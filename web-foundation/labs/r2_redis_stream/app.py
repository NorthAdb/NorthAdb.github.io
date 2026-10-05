"""r2 端点：SSE 的"历史"部分来自 Redis Stream（跨进程可用）。

关键行为变化（对照 r1）：
- 任务不在本进程运行也能回放：只要 Stream 存在，XRANGE 就能补出完整历史
- 断线续传跨进程成立：Last-Event-ID 是业务 seq，任何进程读同一个 Stream
"""

import asyncio
import json
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from redis_client import get_redis

from .agent import RUNNING, run_agent_task, read_stream, stream_key
from .events import EventType

app = FastAPI(title="r2 · 事件日志外移到 Redis Stream")

R = get_redis()
TASK_RUNNERS: dict[str, asyncio.Task] = {}


def to_sse(ev) -> ServerSentEvent:
    return ServerSentEvent(event=ev.type.value, id=str(ev.seq), data=ev.model_dump(mode="json"))


class TaskStore:
    """与 r1 相同的 Hash 任务表（任务元数据外移在 r1 已完成）。"""

    KEY = "agent:tasks"

    def create(self, goal: str) -> dict:
        import uuid as _uuid

        task_id = _uuid.uuid4().hex[:8]
        task = {"task_id": task_id, "goal": goal, "state": "running"}
        R.hset(self.KEY, task_id, json.dumps(task, ensure_ascii=False))
        return task

    def get(self, task_id: str) -> dict | None:
        raw = R.hget(self.KEY, task_id)
        return json.loads(raw) if raw else None

    def set_state(self, task_id: str, state: str) -> None:
        task = self.get(task_id)
        if task:
            task["state"] = state
            R.hset(self.KEY, task_id, json.dumps(task, ensure_ascii=False))

    def all(self) -> list[dict]:
        return [json.loads(v) for v in R.hvals(self.KEY)]


STORE = TaskStore()


def _ensure_task(task_id: str) -> str:
    """任务要么在本进程运行、要么有 Stream 历史；两者皆无 → 404。"""
    if task_id in RUNNING or R.exists(stream_key(task_id)):
        return task_id
    raise HTTPException(status_code=404, detail="task not found")


class GoalRequest(BaseModel):
    goal: str


@app.post("/agent/tasks")
async def create_task(req: GoalRequest) -> dict:
    task = STORE.create(req.goal)
    TASK_RUNNERS[task["task_id"]] = asyncio.create_task(
        run_agent_task(task["task_id"], STORE)
    )
    return task


@app.get("/agent/tasks")
async def list_tasks() -> list[dict]:
    return STORE.all()


@app.get("/agent/tasks/{task_id}", dependencies=[Depends(_ensure_task)])
async def get_task(task_id: str) -> dict:
    task = STORE.get(task_id)
    return task or {"task_id": task_id, "state": "unknown"}


@app.get("/agent/tasks/{task_id}/events", response_class=EventSourceResponse)
async def task_events(
    task_id: str = Depends(_ensure_task),
    last_event_id: Annotated[str | None, Header()] = None,
):
    """三段式：Stream 回放（跨进程）→ 本进程实时跟随（若有）→ 终态关流。

    注意：端点函数必须自身是 async generator（learning-records/0002 的头号坑，
    `return EventSourceResponse(gen())` 风格在此必然报 'coroutine' object is not iterable）。
    """
    sent = int(last_event_id) if last_event_id else 0
    terminal = {EventType.done, EventType.agent_error}

    # 1) 历史回放：任何进程都能做（数据在 Redis，不在内存）
    for ev in read_stream(task_id, after_seq=sent):
        sent = ev.seq
        yield to_sse(ev)
        if ev.type in terminal:
            return

    # 2) 实时跟随：仅当任务在本进程运行
    task = RUNNING.get(task_id)
    if task is None:
        return
    q = task.subscribe()
    try:
        while True:
            ev = await q.get()
            if ev.seq > sent:
                sent = ev.seq
                yield to_sse(ev)
            if ev.type in terminal:
                break
    finally:
        task.unsubscribe(q)
