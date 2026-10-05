"""r3：完整的多进程 Agent Server——v7 的所有能力 + 跨 Worker。

三个进程内结构全部外移（对照 v7 → r1/r2 的演进）：
- TASKS      → Hash（r1）
- buffer     → Stream（r2）
- ControlHub → Pub/Sub（本实验新增）

关键设计（v7 没有的新问题）：
1. seq 用 Redis INCR——跨进程也必须单调（v6/v7 里 len(buffer) 只在本进程有意义）
2. 控制指令的路由：暂停/审批的"闸门"（Event/Future）在**属主进程**的协程里，
   任何进程收到 WS 命令后发布到 `agent:control:{id}` 频道，属主监听并执行——
   这就是控制平面的"路由"问题
3. 状态反馈不再需要 WS 镜像：属主执行命令后 emit task_state 事件，
   走同一条 Stream/Pub/Sub 数据面，所有订阅者（包括 UI）自然可见
"""

import asyncio
import json
from enum import Enum
from typing import Any

from redis_client import get_async_redis

from .events import AgentEvent, EventType

R = get_async_redis()


class TaskState(str, Enum):
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    ERROR = "error"


def stream_key(task_id: str) -> str:
    return f"agent:{task_id}:events"


def control_channel(task_id: str) -> str:
    return f"agent:control:{task_id}"


def events_channel(task_id: str) -> str:
    return f"agent:events:{task_id}"


async def read_stream(task_id: str, after_seq: int = 0) -> list[AgentEvent]:
    """XRANGE 全量读取 + 按 seq 过滤（r2 同款；生产用增量游标，见 README）。"""
    out: list[AgentEvent] = []
    if not await R.exists(stream_key(task_id)):
        return out
    for _entry_id, fields in await R.xrange(stream_key(task_id), "-", "+"):
        seq = int(fields["seq"])
        if seq <= after_seq:
            continue
        out.append(
            AgentEvent(
                seq=seq,
                type=fields["type"],
                task_id=task_id,
                timestamp=fields.get("ts", ""),
                data=json.loads(fields.get("data", "{}")),
            )
        )
    return out


class AgentTask:
    """运行体已经"薄"了：只有 emit——写 Stream（历史）+ 发 Pub/Sub（实时）。

    v7 里的 buffer/订阅者队列都不需要了：实时性由 Pub/Sub 承担，
    历史由 Stream 承担，SSE 订阅者自己决定"从哪一 seq 开始要"。
    """

    def __init__(self, task_id: str, goal: str) -> None:
        self.id = task_id
        self.goal = goal

    async def emit(self, type_: EventType, **data: Any) -> AgentEvent:
        seq = await R.incr(f"agent:{self.id}:seq")  # INCR：跨进程原子的单调计数器
        ev = AgentEvent(seq=seq, type=type_, task_id=self.id, data=data)
        await R.xadd(
            stream_key(self.id),
            {
                "seq": ev.seq,
                "type": ev.type.value,
                "ts": ev.timestamp,
                "data": json.dumps(ev.data, ensure_ascii=False),
            },
        )
        await R.publish(events_channel(self.id), ev.model_dump_json())
        return ev


class Controls:
    """控制闸门——住在**属主进程**（runner 所在处）。

    其他进程只能通过 control 频道发命令，由属主的 listener 执行。
    """

    def __init__(self) -> None:
        self.resume = asyncio.Event()
        self.resume.set()  # 有信号 = 允许运行
        self.approval: asyncio.Future[bool] | None = None

    async def checkpoint(self) -> None:
        await self.resume.wait()

    async def wait_approval(self) -> bool:
        self.approval = asyncio.get_running_loop().create_future()
        approved = await self.approval
        self.approval = None
        return approved

    def resolve(self, approved: bool) -> bool:
        if self.approval is not None and not self.approval.done():
            self.approval.set_result(approved)
            return True
        return False


class Runtime:
    """把一次任务运行的相关句柄收拢，便于 listener 与 runner 互相触达。"""

    def __init__(self, task_id: str, goal: str) -> None:
        self.task = AgentTask(task_id, goal)
        self.controls = Controls()
        self.runner: asyncio.Task | None = None
        self.listener: asyncio.Task | None = None


async def control_listener(rt: Runtime) -> None:
    """属主进程的命令执行器：订阅 control 频道，把命令落到闸门上。"""
    pubsub = R.pubsub(ignore_subscribe_messages=True)
    await pubsub.subscribe(control_channel(rt.task.id))
    try:
        while True:
            msg = await pubsub.get_message(timeout=1.0)
            if msg is None or msg.get("data") is None:
                continue
            cmd = json.loads(msg["data"])
            action = cmd.get("action")
            if action == "pause":
                rt.controls.resume.clear()
                await rt.task.emit(EventType.task_state, state="paused")
            elif action == "resume":
                rt.controls.resume.set()
                await rt.task.emit(EventType.task_state, state="running")
            elif action == "cancel":
                if rt.runner is not None:
                    rt.runner.cancel()
            elif action in ("approve", "reject"):
                rt.controls.resolve(action == "approve")
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.close()


async def run_agent_task(rt: Runtime, store: Any) -> None:
    task = rt.task
    try:
        await task.emit(EventType.agent_started, goal=task.goal)

        await rt.controls.checkpoint()
        await task.emit(EventType.step_started, name="rag_retrieve")
        await task.emit(EventType.rag_search, query=task.goal, top_k=3)
        for _ in range(6):
            await asyncio.sleep(0.5)
            await rt.controls.checkpoint()  # 分片等待：暂停/取消响应更及时
        docs = ["《RAG 综述》第 2 章", "知识库：产品 FAQ", "2025 年度技术报告"]
        await task.emit(EventType.rag_result, documents=docs)
        await task.emit(EventType.step_finished, name="rag_retrieve")

        await rt.controls.checkpoint()
        await task.emit(
            EventType.tool_call,
            tool="send_email",
            arguments={"to": "boss@corp.com", "subject": "周报"},
            requires_approval=True,
        )
        approved = await rt.controls.wait_approval()
        if approved:
            await asyncio.sleep(0.8)
            await task.emit(EventType.tool_result, tool="send_email", result="邮件已发送")
        else:
            await task.emit(
                EventType.tool_result, tool="send_email", result="用户拒绝了该工具调用"
            )

        await rt.controls.checkpoint()
        await task.emit(EventType.step_started, name="generate")
        answer = "事件经 Redis Stream 存日志、Pub/Sub 做实时广播：两个 Worker 互相看不见，却配合无误。"
        for i in range(0, len(answer), 2):
            await rt.controls.checkpoint()
            await task.emit(EventType.token, text=answer[i : i + 2])
            await asyncio.sleep(0.12)
        await task.emit(EventType.step_finished, name="generate")

        await store.set_state(task.id, TaskState.DONE.value)
        await task.emit(EventType.done)
    except asyncio.CancelledError:
        await store.set_state(task.id, TaskState.CANCELLED.value)
        await task.emit(EventType.agent_error, message="任务被用户取消", cancelled=True)
    except Exception as exc:
        await store.set_state(task.id, TaskState.ERROR.value)
        await task.emit(EventType.agent_error, message=str(exc))
    finally:
        if rt.listener is not None:
            rt.listener.cancel()
