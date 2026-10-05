"""v7：Agent 运行时——可暂停、可取消、可审批的长任务 + 事件广播基础设施。

与 v6 的关键区别：
1. Agent 不再是"与 HTTP 连接同生共死"的 generator，而是 asyncio.create_task 启动的**后台任务**；
   SSE 断开、浏览器关闭，它都继续跑。
2. 事件先进任务的事件缓冲（buffer），SSE 订阅者只是" followers"之一 → 断线可按 seq 续传。
3. 控制原语：resume Event（暂停/恢复）、approval Future（人工审批）、runner.cancel()（取消）。
4. ControlHub：把状态变化镜像推给所有 WebSocket 控制连接（v8 会升级成 Redis 广播）。
"""

import asyncio
import uuid
from enum import Enum
from typing import Any

from .events import AgentEvent, EventType


class TaskState(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    DONE = "done"
    CANCELLED = "cancelled"
    ERROR = "error"


class ControlHub:
    """WebSocket 控制通道的"广播站"：每条控制连接登记在这里，
    运行时的状态变化（审批请求、暂停、结束……）镜像推送给它们。"""

    def __init__(self) -> None:
        self.clients: set[Any] = set()

    def broadcast(self, payload: dict) -> None:
        for ws in list(self.clients):
            asyncio.create_task(self._safe_send(ws, payload))

    async def _safe_send(self, ws: Any, payload: dict) -> None:
        try:
            await ws.send_json(payload)
        except Exception:
            self.clients.discard(ws)  # 死连接就地清理


hub = ControlHub()


class AgentTask:
    """一个正在运行的 Agent 任务：事件缓冲 + 订阅者队列 + 控制原语。"""

    def __init__(self, goal: str) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.goal = goal
        self.state = TaskState.RUNNING
        self.buffer: list[AgentEvent] = []                      # 全量事件日志（重放依据）
        self._subscribers: list[asyncio.Queue[AgentEvent]] = []
        self._resume = asyncio.Event()
        self._resume.set()                                      # Event 有信号 = 允许运行
        self._approval: asyncio.Future[bool] | None = None
        self.runner: asyncio.Task | None = None

    # ---------- 事件出口 ----------

    async def emit(self, type_: EventType, **data: Any) -> AgentEvent:
        ev = AgentEvent(seq=len(self.buffer) + 1, type=type_, task_id=self.id, data=data)
        self.buffer.append(ev)
        for q in list(self._subscribers):
            q.put_nowait(ev)                                    # 无界队列：发事件永不清除阻塞
        return ev

    def subscribe(self) -> asyncio.Queue[AgentEvent]:
        q: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[AgentEvent]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    # ---------- 控制原语 ----------

    async def checkpoint(self) -> None:
        """暂停闸门：被暂停时 await 在这里挂起；恢复后从此继续。"""
        await self._resume.wait()

    async def wait_approval(self) -> bool:
        """人工审批闸门：挂起等待 approve/reject 来 resolve 这个 Future。"""
        self.state = TaskState.WAITING_APPROVAL
        hub.broadcast({"type": "approval_required", "task_id": self.id})
        self._approval = asyncio.get_running_loop().create_future()
        approved = await self._approval
        self._approval = None
        self.state = TaskState.RUNNING
        hub.broadcast({"type": "state_update", "task_id": self.id, "state": "running"})
        return approved

    def resolve_approval(self, approved: bool) -> bool:
        if self._approval is not None and not self._approval.done():
            self._approval.set_result(approved)
            return True
        return False


# ---------- Agent 主体：一个带检查点的长任务 ----------


async def run_agent_task(task: AgentTask) -> None:
    try:
        await task.emit(EventType.agent_started, goal=task.goal)

        # 步骤 1：RAG 检索。分段 sleep + 每段后过闸门 → 暂停/取消的响应手感更好
        await task.checkpoint()
        await task.emit(EventType.step_started, name="rag_retrieve")
        await task.emit(EventType.rag_search, query=task.goal, top_k=3)
        for _ in range(6):
            await asyncio.sleep(0.5)
            await task.checkpoint()
        docs = ["《RAG 综述》第 2 章", "知识库：产品 FAQ", "2025 年度技术报告"]
        await task.emit(EventType.rag_result, documents=docs)
        await task.emit(EventType.step_finished, name="rag_retrieve")

        # 步骤 2：需要人工审批的工具调用（human-in-the-loop）
        await task.checkpoint()
        await task.emit(
            EventType.tool_call,
            tool="send_email",
            arguments={"to": "boss@corp.com", "subject": "周报"},
            requires_approval=True,
        )
        approved = await task.wait_approval()
        if approved:
            await asyncio.sleep(1)
            await task.emit(EventType.tool_result, tool="send_email", result="邮件已发送")
        else:
            await task.emit(
                EventType.tool_result, tool="send_email", result="用户拒绝了该工具调用"
            )

        # 步骤 3：逐 token 生成
        await task.checkpoint()
        await task.emit(EventType.step_started, name="generate")
        answer = "根据检索结果与审批后的工具输出：本周周报已由 Agent 代拟完毕，请查收。"
        for i in range(0, len(answer), 2):
            await task.checkpoint()
            await task.emit(EventType.token, text=answer[i : i + 2])
            await asyncio.sleep(0.15)
        await task.emit(EventType.step_finished, name="generate")

        task.state = TaskState.DONE
        await task.emit(EventType.done)
        hub.broadcast({"type": "state_update", "task_id": task.id, "state": "done"})
    except asyncio.CancelledError:
        # 取消不是错误：优雅收尾并通知所有订阅者（通常建议重新 raise，
        # 这里 runner 是我们自有的后台任务，吞掉取消以完成事件广播）
        task.state = TaskState.CANCELLED
        await task.emit(EventType.agent_error, message="任务被用户取消", cancelled=True)
        hub.broadcast({"type": "state_update", "task_id": task.id, "state": "cancelled"})
    except Exception as exc:
        task.state = TaskState.ERROR
        await task.emit(EventType.agent_error, message=str(exc))
        hub.broadcast({"type": "state_update", "task_id": task.id, "state": "error"})
