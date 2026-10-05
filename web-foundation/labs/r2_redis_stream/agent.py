"""r2：事件日志外移到 Redis Stream——事件不再属于任何进程。

与 r1 的差别：
- AgentTask.buffer（内存列表）→ Redis Stream `agent:{task_id}:events`
- seq 从 Redis INCR 取（跨进程原子的单调计数器），不再是 len(buffer)+1
- 收益：**任何一个进程**都能回放任何任务的完整事件流（XRANGE），
  Last-Event-ID 断线续传从此跨进程成立
- 实时跟随仍是进程内订阅者队列（跨进程实时是 r3 的 Pub/Sub）

启动：python -m uvicorn r2_redis_stream.app:app --port 18902 --reload
"""

import asyncio
import json
from typing import Any

from redis_client import get_redis

from .events import AgentEvent, EventType

R = get_redis()


def stream_key(task_id: str) -> str:
    return f"agent:{task_id}:events"


def read_stream(task_id: str, after_seq: int = 0) -> list[AgentEvent]:
    """XRANGE 全量读取后按 seq 字段过滤。

    为什么不用 XRANGE 的排他区间直接从断点读？我们的续传位点是**业务 seq**
    （任务内单调），而 Stream 条目 ID 是时间戳形态（ms-us），两者不同轴。
    教学从简全量拉取+过滤；生产中事件量大时，把业务 seq 编码进 Stream 条目 ID
    或维护"seq → entry id"索引再增量 XRANGE。
    """
    out: list[AgentEvent] = []
    if not R.exists(stream_key(task_id)):
        return out
    for entry_id, fields in R.xrange(stream_key(task_id), "-", "+"):
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
    """运行体：只有订阅者队列在内存，事件本身全部走 Stream。"""

    def __init__(self, task_id: str, goal: str) -> None:
        self.id = task_id
        self.goal = goal
        self._subscribers: list[asyncio.Queue[AgentEvent]] = []

    async def emit(self, type_: EventType, **data: Any) -> AgentEvent:
        seq = R.incr(f"agent:{self.id}:seq")  # 跨进程原子的单调计数器
        ev = AgentEvent(seq=seq, type=type_, task_id=self.id, data=data)
        R.xadd(
            stream_key(self.id),
            {
                "seq": ev.seq,
                "type": ev.type.value,
                "ts": ev.timestamp,
                "data": json.dumps(ev.data, ensure_ascii=False),
            },
        )
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
        answer = "事件已经写进 Redis Stream：换一个进程也能完整回放这段回答。"
        for i in range(0, len(answer), 2):
            await task.emit(EventType.token, text=answer[i : i + 2])
            await asyncio.sleep(0.08)
        await task.emit(EventType.step_finished, name="generate")

        store.set_state(task_id, "done")
        await task.emit(EventType.done)
    except asyncio.CancelledError:
        store.set_state(task_id, "cancelled")
        await task.emit(EventType.agent_error, message="任务被用户取消", cancelled=True)
    except Exception as exc:
        store.set_state(task_id, "error")
        await task.emit(EventType.agent_error, message=str(exc))
    finally:
        RUNNING.pop(task_id, None)
