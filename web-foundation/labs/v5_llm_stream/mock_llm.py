"""实验 v5 的 mock LLM：不用 API Key 也能跑通"token 流"全链路。

真实 LLM 的 streaming 本质与此相同：SDK 拿到的是服务器推送的字节块，
我们只是把它换成"按字符切分 + 延时"来模拟。
"""

import asyncio
from collections.abc import AsyncIterator


class MockLLM:
    """极简"大模型"：把回复按字符吐出，模拟 token 一个个到达。"""

    REPLY = (
        "RAG 是一种检索增强生成技术：先从知识库检索与问题相关的文档，"
        "再把文档内容和问题一起交给大模型，让它基于资料作答，"
        "从而减少幻觉、支持私有知识。"
    )

    async def stream_tokens(self, prompt: str, delay: float = 0.06) -> AsyncIterator[str]:
        # prompt 在 mock 里不参与生成，但接口签名与真实 SDK 对齐，方便无缝替换
        for ch in self.REPLY:
            yield ch
            await asyncio.sleep(delay)

    async def complete(self, prompt: str) -> str:
        """非流式接口：攒齐再返回。对照实验用——感受'转圈圈'与'打字机'的差别。"""
        await asyncio.sleep(2)
        return self.REPLY
