"""实验 v5：LLM Token Streaming 全链路——LLM SDK → async generator → SSE → 浏览器。

启动：python -m uvicorn v5_llm_stream.app:app --port 8805 --reload
观察：
  # 对照组：非流式，等 2 秒一次性返回
  curl -X POST http://127.0.0.1:8805/chat -H "Content-Type: application/json" -d '{"text": "什么是RAG"}'
  # 流式：SSE token 事件一个个到达，最后一个事件 data 是裸的 [DONE]
  curl -N -X POST http://127.0.0.1:8805/chat/stream -H "Content-Type: application/json" -d '{"text": "什么是RAG"}'
  # 浏览器：打开 http://127.0.0.1:8805/ 看打字机效果（对照/流式两个按钮）

配置 OPENAI_API_KEY 环境变量后（可选），/chat/stream 自动切换为真实 OpenAI 流式接口，
其余代码零改动——这就是接口对齐的好处。
"""

import os
from collections.abc import AsyncIterable

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from .mock_llm import MockLLM

app = FastAPI(title="v5 LLM Token Streaming")

llm = MockLLM()


class Prompt(BaseModel):
    text: str


@app.post("/chat")
async def chat(prompt: Prompt) -> dict:
    """非流式：整个回答生成完才返回。用户体验问题：等待期无任何反馈。"""
    reply = await llm.complete(prompt.text)
    return {"reply": reply}


# ---------- 流式链路的核心 ----------


async def mock_stream(prompt: str) -> AsyncIterable[ServerSentEvent]:
    async for token in llm.stream_tokens(prompt):
        yield ServerSentEvent(event="token", data=token)  # 一个 token → 一条 SSE 事件


async def openai_stream(prompt: str) -> AsyncIterable[ServerSentEvent]:
    """真实 LLM：openai SDK 的流式接口。token 的来源变了，下游完全一样。"""
    from openai import AsyncOpenAI

    client = AsyncOpenAI()  # 读 OPENAI_API_KEY / OPENAI_BASE_URL 环境变量
    stream = await client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:  # 部分 chunk 的 delta 可能为 None（如角色帧）
            yield ServerSentEvent(event="token", data=delta)


@app.post("/chat/stream", response_class=EventSourceResponse)
async def chat_stream(prompt: Prompt):
    """端点函数本身是 async generator（fastapi.sse 的要求）：
    选择 generator，逐事件 yield，最后补一个 done 哨兵。"""
    gen = openai_stream(prompt.text) if os.getenv("OPENAI_API_KEY") else mock_stream(prompt.text)
    async for ev in gen:
        yield ev
    # OpenAI 约定：流结束发裸字符串 [DONE]。raw_data 不做 JSON 编码
    yield ServerSentEvent(event="done", raw_data="[DONE]")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("v5_llm_stream/index.html")
