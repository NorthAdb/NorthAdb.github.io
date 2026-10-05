"""v6：一个会"直播过程"的假 Agent——RAG 检索、工具调用、逐 token 生成全部以事件形式吐出。

Agent 本身与 Web 框架零耦合：run() 是一个 async generator，
调用方（app.py 的 SSE 端点）只负责把事件装进 SSE 信封。
这就是"Agent Runtime"与"通信层"的分界线——module-4 的核心思想。
"""

import asyncio
from collections.abc import AsyncIterator

from .events import AgentEvent, EventType


class FakeRAGAgent:
    def __init__(self) -> None:
        self._seq = 0

    async def _emit(self, task_id: str, type_: EventType, **data) -> AgentEvent:
        self._seq += 1
        return AgentEvent(seq=self._seq, type=type_, task_id=task_id, data=data)

    async def run(self, task_id: str, question: str) -> AsyncIterator[AgentEvent]:
        # 1. 生命周期开始
        yield await self._emit(task_id, EventType.agent_started, question=question)

        # 2. RAG 步骤：三段式——步骤开始 / 过程事件 / 结果事件 / 步骤结束
        yield await self._emit(task_id, EventType.step_started, name="rag_retrieve")
        yield await self._emit(task_id, EventType.rag_search, query=question, top_k=3)
        await asyncio.sleep(1.0)  # 模拟向量检索耗时
        docs = ["《RAG 综述》第 2 章", "知识库：产品 FAQ", "2025 年度技术报告"]
        yield await self._emit(task_id, EventType.rag_result, documents=docs)
        yield await self._emit(task_id, EventType.step_finished, name="rag_retrieve")

        # 3. 工具调用：call 与 result 成对出现
        yield await self._emit(
            task_id, EventType.tool_call, tool="calculator", arguments={"expr": "12*8"}
        )
        await asyncio.sleep(0.5)
        yield await self._emit(task_id, EventType.tool_result, tool="calculator", result="96")

        # 4. 生成步骤：逐 token
        yield await self._emit(task_id, EventType.step_started, name="generate")
        answer = (
            f"根据《{docs[0]}》等资料，并结合计算器算出的 96："
            "检索增强生成的关键在于先查后答。"
        )
        for ch in answer:
            yield await self._emit(task_id, EventType.token, text=ch)
            await asyncio.sleep(0.04)
        yield await self._emit(task_id, EventType.step_finished, name="generate")

        # 5. 生命周期结束
        yield await self._emit(task_id, EventType.done)
