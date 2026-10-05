"""r1：把 v7 的任务表（TASKS 字典）外移到 Redis Hash。

与 v7 的差别（对照 labs/v7_agent_server）：
- TASKS: dict → Redis Hash `agent:tasks`（field=task_id，value=任务 JSON）
- 事件缓冲 buffer 和 ControlHub 仍是进程内存（r2/r3 再分别外移）
- 收益：任何进程/任何连接都能读到任务状态（v7 里只有创建任务的那个进程能）

启动：python -m uvicorn r1_redis_tasks.app:app --port 18901 --reload
观察：
  curl -X POST http://127.0.0.1:18901/agent/tasks -H "Content-Type: application/json" -d '{"goal": "r1 demo"}'
  # 另开一个终端，绕过 HTTP 直接查 Redis（等于"另一个进程"在看）：
  docker exec course-redis redis-cli hgetall agent:tasks
  # 或运行跨连接验证脚本：
  python r1_redis_tasks/verify_cross_connection.py
"""

import asyncio
import json
import uuid
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from redis_client import get_redis

from .agent import RUNNING, TaskState, run_agent_task
from .events import AgentEvent, EventType

app = FastAPI(title="r1 · 任务表外移到 Redis Hash")

R = get_redis()  # 整个进程共享一个连接（生产会换连接池，教学从简）

TASK_RUNNERS: dict[str, asyncio.Task] = {}  # 进程内的 asyncio 后台任务（天然不能进 Redis）


def to_sse(ev: AgentEvent) -> ServerSentEvent:
    return ServerSentEvent(event=ev.type.value, id=str(ev.seq), data=ev.model_dump(mode="json"))


class TaskStore:
    """任务表：Redis Hash `agent:tasks`（field=task_id，value=任务 JSON）。

    设计取舍：教学从简用一张总索引 Hash。生产中任务字段多、要按字段更新时，
    更推荐每个任务一条独立 Hash（agent:task:{id}）。
    """

    KEY = "agent:tasks"

    def create(self, goal: str) -> dict:
        task_id = uuid.uuid4().hex[:8]
        task = {"task_id": task_id, "goal": goal, "state": TaskState.RUNNING.value}
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


class GoalRequest(BaseModel):
    goal: str


@app.post("/agent/tasks")
async def create_task(req: GoalRequest) -> dict:
    task = STORE.create(req.goal)
    # 后台任务仍在本进程：控制指令如何跨进程路由是 r3 的主题
    TASK_RUNNERS[task["task_id"]] = asyncio.create_task(
        run_agent_task(task["task_id"], STORE)
    )
    return task


@app.get("/agent/tasks")
async def list_tasks() -> list[dict]:
    return STORE.all()


@app.get("/agent/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    task = STORE.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


async def _running_task(task_id: str) -> Any:
    """依赖：任务不在本进程运行 → 404（响应开始前抛出才有效）。

    r1 的刻意局限：任务结束后事件随 RUNNING 登记簿一起消失——
    跨进程/跨时间的事件回放要等 r2 的 Redis Stream。
    """
    task = RUNNING.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=404,
            detail="task not running in this process（r1 局限：事件仍在内存，见 README）",
        )
    return task


@app.get("/agent/tasks/{task_id}/events", response_class=EventSourceResponse)
async def task_events(
    task: Any = Depends(_running_task),
    last_event_id: Annotated[str | None, Header()] = None,
):
    """事件直播仍是进程内存版（v7 同款三步：先订阅 → 补历史 → 实时跟随）。"""
    q = task.subscribe()
    sent = int(last_event_id) if last_event_id else 0
    terminal = {EventType.done, EventType.agent_error}
    try:
        for ev in list(task.buffer):
            if ev.seq > sent:
                sent = ev.seq
                yield to_sse(ev)
        while True:
            ev = await q.get()
            if ev.seq > sent:
                sent = ev.seq
                yield to_sse(ev)
            if ev.type in terminal:
                break
    finally:
        task.unsubscribe(q)
