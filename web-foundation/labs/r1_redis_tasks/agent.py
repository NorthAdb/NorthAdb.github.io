"""r1 的 Agent 主体：事件缓冲与订阅者队列仍是**进程内存**（与 v7 相同）。

r1 只外移任务表（Hash）。刻意保留这个局限：
- 事件在内存 → 换一个进程就看不到（r2 用 Redis Stream 解决）
- 后台任务在进程内 → 控制指令无法跨进程路由（r3 用 Pub/Sub 解决）
"""

import asyncio
from enum import Enum
from typing import Any

from .events import AgentEvent, EventType


class TaskState(str, Enum):
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    ERROR = "error"


class AgentTask:
    """进程内运行体：全量事件缓冲 + 订阅者队列（v7 同款）。"""

    def __init__(self, task_id: str, goal: str) -> None:
        self.id = task_id
        self.goal = goal
        self.buffer: list[AgentEvent] = []
        self._subscribers: list[asyncio.Queue[AgentEvent]] = []

    async def emit(self, type_: EventType, **data: Any) -> AgentEvent:
        ev = AgentEvent(seq=len(self.buffer) + 1, type=type_, task_id=self.id, data=data)
        self.buffer.append(ev)
        for q in list(self._subscribers):
            q.put_nowait(ev)
        return ev

    def subscribe(self) -> asyncio.Queue[AgentEvent]:
        q: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[AgentEvent]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)


RUNNING: dict[str, AgentTask] = {}


async def run_agent_task(task_id: str, store: Any) -> None:
    meta = store.get(task_id) or {"goal": "(unknown)"}
    task = AgentTask(task_id, meta["goal"])
    RUNNING[task_id] = task
    try:
        await task.emit(EventType.agent_started, goal=task.goal)

        await task.emit(EventType.step_started, name="rag_retrieve")
        await task.emit(EventType.rag_search, query=task.goal, top_k=3)
        for _ in range(3):
            await asyncio.sleep(0.4)
        docs = ["《RAG 综述》第 2 章", "知识库：产品 FAQ", "2025 年度技术报告"]
        await task.emit(EventType.rag_result, documents=docs)
        await task.emit(EventType.step_finished, name="rag_retrieve")

        await task.emit(EventType.step_started, name="generate")
        answer = "任务状态已存入 Redis Hash；事件日志的外移在 r2 完成。"
        for i in range(0, len(answer), 2):
            await task.emit(EventType.token, text=answer[i : i + 2])
            await asyncio.sleep(0.08)
        await task.emit(EventType.step_finished, name="generate")

        store.set_state(task_id, TaskState.DONE.value)
        await task.emit(EventType.done)
    except asyncio.CancelledError:
        store.set_state(task_id, TaskState.CANCELLED.value)
        await task.emit(EventType.agent_error, message="任务被用户取消", cancelled=True)
    except Exception as exc:
        store.set_state(task_id, TaskState.ERROR.value)
        await task.emit(EventType.agent_error, message=str(exc))
    finally:
        RUNNING.pop(task_id, None)  # 结束后从进程登记簿移除；历史靠 r2 的 Stream
