"""实验 v7：Mini Agent Server——SSE 负责"直播"，WebSocket 负责"遥控"。

启动：python -m uvicorn v7_agent_server.app:app --port 8807 --reload
观察：
  浏览器打开 http://127.0.0.1:8807/  → 完整交互界面（推荐）
  自动化验证：python v7_agent_server/test_flow.py   （需服务已启动）

架构分工（module-4/5 的核心结论）：
  SSE  GET /agent/tasks/{id}/events   Agent → UI 的单向事件直播（可断线续传）
  WS   /ws/control                    UI → Agent 的实时控制 + 状态镜像
"""

import asyncio

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel
from typing import Annotated

from .agent import AgentTask, TaskState, hub, run_agent_task
from .events import AgentEvent, EventType

app = FastAPI(title="v7 Mini Agent Server")

TASKS: dict[str, AgentTask] = {}


def to_sse(ev: AgentEvent) -> ServerSentEvent:
    return ServerSentEvent(event=ev.type.value, id=str(ev.seq), data=ev.model_dump(mode="json"))


def _get_task(task_id: str) -> AgentTask:
    """依赖：任务不存在时在响应开始前返回 404（不能在 SSE generator 里 raise）。"""
    task = TASKS.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


# ---------- 任务生命周期：REST 入口 ----------


class GoalRequest(BaseModel):
    goal: str


@app.post("/agent/tasks")
async def create_task(req: GoalRequest) -> dict:
    task = AgentTask(req.goal)
    TASKS[task.id] = task
    # 关键：Agent 以后台任务运行，与任何 HTTP 连接解耦
    task.runner = asyncio.create_task(run_agent_task(task))
    return {"task_id": task.id, "goal": task.goal}


@app.get("/agent/tasks")
async def list_tasks() -> list[dict]:
    return [
        {"task_id": t.id, "goal": t.goal, "state": t.state.value, "events": len(t.buffer)}
        for t in TASKS.values()
    ]


@app.get("/agent/tasks/{task_id}")
async def get_task(task: AgentTask = Depends(_get_task)) -> dict:
    return {"task_id": task.id, "goal": task.goal, "state": task.state.value}


# ---------- 事件直播：SSE + 断线续传 ----------


@app.get("/agent/tasks/{task_id}/events", response_class=EventSourceResponse)
async def task_events(
    last_event_id: Annotated[str | None, Header()] = None,
    task: AgentTask = Depends(_get_task),
):
    """端点函数自身是 async generator（fastapi.sse 的要求）；404 校验放在依赖里。

    不漏不重的三步：
      1) 先订阅队列（新事件从此刻开始积累）
      2) 再补发 buffer 里 seq > last_event_id 的历史事件
      3) 实时循环中用 sent 水位线对重叠区去重
    """
    q = task.subscribe()
    sent = int(last_event_id) if last_event_id else 0
    terminal = {EventType.done, EventType.agent_error}
    try:
        for ev in list(task.buffer):            # 1) 补发断线期间错过的事件
            if ev.seq > sent:
                sent = ev.seq
                yield to_sse(ev)
        while True:                              # 2) 实时跟随
            ev = await q.get()
            if ev.seq > sent:                    # 订阅与补发的重叠区去重
                sent = ev.seq
                yield to_sse(ev)
            if ev.type in terminal:
                break                            # 终态事件发出后关闭本次流
    finally:
        task.unsubscribe(q)


# ---------- 控制通道：WebSocket ----------


async def apply_command(task: AgentTask, action: str) -> str:
    if action == "pause":
        task._resume.clear()
        task.state = TaskState.PAUSED
        hub.broadcast({"type": "state_update", "task_id": task.id, "state": "paused"})
        return "paused"
    if action == "resume":
        task._resume.set()
        task.state = TaskState.RUNNING
        hub.broadcast({"type": "state_update", "task_id": task.id, "state": "running"})
        return "resumed"
    if action == "cancel":
        if task.runner is not None:
            task.runner.cancel()  # CancelledError 会在 agent 的检查点处被接住
        return "cancelling"
    if action in ("approve", "reject"):
        ok = task.resolve_approval(action == "approve")
        return "resolved" if ok else "no pending approval"
    return f"unknown action: {action}"


@app.websocket("/ws/control")
async def ws_control(websocket: WebSocket) -> None:
    await websocket.accept()
    hub.clients.add(websocket)
    try:
        while True:
            cmd = await websocket.receive_json()  # {"task_id": "...", "action": "pause"}
            task = TASKS.get(cmd.get("task_id", ""))
            if task is None:
                await websocket.send_json({"ok": False, "error": "task not found"})
                continue
            result = await apply_command(task, cmd.get("action", ""))
            await websocket.send_json(
                {"ok": True, "action": cmd.get("action"), "result": result, "state": task.state.value}
            )
    except WebSocketDisconnect:
        hub.clients.discard(websocket)


# ---------- 界面 ----------


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("v7_agent_server/index.html")
