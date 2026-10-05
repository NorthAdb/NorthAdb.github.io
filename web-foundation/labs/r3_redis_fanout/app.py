"""r3 端点：与 v7 形态一致，但每个端点都能在**任何进程**上正确工作。

对照 v7 的三个替换：
- TASKS dict          → Hash（store.py）
- buffer + 订阅者队列 → Stream（回放）+ Pub/Sub（实时）
- ControlHub 单进程   → control 频道（属主进程执行）
"""

import asyncio
import contextlib
import json
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from redis_client import get_async_redis

from .agent import Runtime, control_listener, read_stream, run_agent_task, stream_key
from .events import AgentEvent, EventType
from .store import STORE


@asynccontextmanager
async def lifespan(app: FastAPI):
    """进程启动时拉起 Redis→本地队列 的桥接器，退出时收尾。"""
    app.state.bridge = asyncio.create_task(event_bridge())
    yield
    app.state.bridge.cancel()


app = FastAPI(title="r3 · 多进程 Agent Server（Redis 数据面 + 控制面）", lifespan=lifespan)

R = get_async_redis()

TASK_RUNNERS: dict[str, Runtime] = {}

# 本进程的 SSE 订阅者：task_id → 队列集合。
# 实时事件由唯一的 event_bridge 从 Redis Pub/Sub 收下来分发（v7 ControlHub 的分布式版）。
LOCAL_QUEUES: dict[str, set[asyncio.Queue[AgentEvent]]] = {}


async def event_bridge() -> None:
    """进程内唯一的 Pub/Sub 桥：psubscribe 所有任务的事件频道 → 投给本地订阅队列。

    为什么不让每个 SSE 连接各自订阅 Pub/Sub？连接一断一建都要重建订阅，
    且多个长挂连接共享一个进程级桥更省连接、也更好控制取消。
    """
    pubsub = R.pubsub(ignore_subscribe_messages=True)
    await pubsub.psubscribe("agent:events:*")
    try:
        while True:
            msg = await pubsub.get_message(timeout=1.0)
            if msg is None or msg.get("data") is None:
                continue
            ev = AgentEvent.model_validate_json(msg["data"])
            for q in list(LOCAL_QUEUES.get(ev.task_id, ())):
                q.put_nowait(ev)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.close()


def to_sse(ev: AgentEvent) -> ServerSentEvent:
    return ServerSentEvent(event=ev.type.value, id=str(ev.seq), data=ev.model_dump(mode="json"))


async def _ensure_task(task_id: str) -> str:
    if task_id in TASK_RUNNERS or await R.exists(stream_key(task_id)):
        return task_id
    raise HTTPException(status_code=404, detail="task not found")


class GoalRequest(BaseModel):
    goal: str


@app.post("/agent/tasks")
async def create_task(req: GoalRequest) -> dict:
    task = await STORE.create(req.goal)
    rt = Runtime(task["task_id"], req.goal)
    TASK_RUNNERS[task["task_id"]] = rt
    # 属主进程：runner（闸门所在）+ listener（命令执行器，r3 新增角色）
    rt.runner = asyncio.create_task(run_agent_task(rt, STORE))
    rt.listener = asyncio.create_task(control_listener(rt))
    return task


@app.get("/agent/tasks")
async def list_tasks() -> list[dict]:
    return await STORE.all()


@app.get("/agent/tasks/{task_id}", dependencies=[Depends(_ensure_task)])
async def get_task(task_id: str) -> dict:
    return await STORE.get(task_id) or {"task_id": task_id, "state": "unknown"}


@app.get("/agent/tasks/{task_id}/events", response_class=EventSourceResponse)
async def task_events(
    task_id: str = Depends(_ensure_task),
    last_event_id: Annotated[str | None, Header()] = None,
):
    """三段式（全分布式版）：
    1) XRANGE 回放历史（任何进程）
    2) 从本进程桥接队列跟随实时（桥接器从 Redis Pub/Sub 收，任何进程都有桥）
    3) 终态事件后关流
    """
    sent = int(last_event_id) if last_event_id else 0
    terminal = {EventType.done, EventType.agent_error}

    for ev in await read_stream(task_id, after_seq=sent):
        sent = ev.seq
        yield to_sse(ev)
        if ev.type in terminal:
            return

    q: asyncio.Queue[AgentEvent] = asyncio.Queue()
    LOCAL_QUEUES.setdefault(task_id, set()).add(q)
    try:
        while True:
            ev = await q.get()
            if ev.seq > sent:  # 回放与实时之间的重叠区去重
                sent = ev.seq
                yield to_sse(ev)
            if ev.type in terminal:
                break
    finally:
        LOCAL_QUEUES[task_id].discard(q)


@app.websocket("/ws/control")
async def ws_control(websocket: WebSocket) -> None:
    """控制通道：只负责一件事——把命令发布到 control 频道。

    谁执行？属主进程的 listener。WS 连接落在哪个 Worker 根本无所谓，
    这就是控制平面用 Pub/Sub 做"路由"的含义。
    """
    await websocket.accept()
    try:
        while True:
            cmd = await websocket.receive_json()  # {"task_id": "...", "action": "pause"}
            if not await R.hexists("agent:tasks", cmd.get("task_id", "")):
                await websocket.send_json({"ok": False, "error": "task not found"})
                continue
            await R.publish(f"agent:control:{cmd['task_id']}", json.dumps(cmd))
            await websocket.send_json({"ok": True, "routed": cmd.get("action")})
    except WebSocketDisconnect:
        pass


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("r3_redis_fanout/index.html")
