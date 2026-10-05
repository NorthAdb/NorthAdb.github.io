"""实验 v3b：FastAPI 原生 SSE（fastapi.sse）——生产的默认选择，不重复造轮子。

启动：python -m uvicorn v3_sse.v3b_fastapi_sse:app --port 8803 --reload
观察：
  curl -N http://127.0.0.1:8803/events
  # 断线续传：先收到几个事件后 Ctrl+C，再带着最后收到的 id 重连：
  curl -N -H "Last-Event-ID: 3" http://127.0.0.1:8803/resumable
  # POST + SSE（MCP Streamable HTTP 同款模式）：
  curl -N -X POST http://127.0.0.1:8803/chat/stream -H "Content-Type: application/json" -d '{"text": "hello fastapi sse"}'

重要工程事实（踩坑实录）：
  fastapi.sse 的端点函数**必须自身是 async generator**（函数体里有 yield）。
  `return EventSourceResponse(gen())` 或 `return 某个generator` 都会在请求时
  抛 "'coroutine' object is not iterable"——框架在装饰器阶段就把端点函数本身当作流。
  需要 404 等非 200 语义时，把校验放进 Depends 依赖（依赖在响应开始前执行）。
"""

import asyncio

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel
from typing import Annotated

app = FastAPI(title="v3b FastAPI 原生 SSE")

# file:// 打开的 sse_client.html 是跨源请求（Origin: null），EventSource 走 CORS，
# 实验服务显式放行。生产服务不要配 "*"，要改成前端站点白名单。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 1. 基础事件流：端点函数自己 yield ----------


@app.get("/events", response_class=EventSourceResponse)
async def events():
    """response_class=EventSourceResponse + async generator。

    框架自动处理：text/event-stream 头、no-cache、X-Accel-Buffering: no、
    以及 15 秒无消息时的 comment 心跳（防代理断链）。手写版里那些细节全都不用管了。
    """
    for i in range(1, 9):
        yield ServerSentEvent(event="tick", id=str(i), data={"n": i})
        await asyncio.sleep(1)
    yield ServerSentEvent(event="done", id="8", data={"ok": True})


# ---------- 2. 断线续传：读取浏览器自动回传的 Last-Event-ID ----------

# 生产中这通常是"事件日志/消息队列"；这里用内存列表演示机制。
EVENT_LOG: list[dict] = [{"n": i} for i in range(1, 9)]


@app.get("/resumable", response_class=EventSourceResponse)
async def resumable(last_event_id: Annotated[str | None, Header()] = None):
    """EventSource 断线重连时会带上 `Last-Event-ID: <最后收到的id>`。

    服务端据此"补发错过的事件"，而不是从头再来。
    """
    start = int(last_event_id) + 1 if last_event_id else 1
    for i in range(start, len(EVENT_LOG) + 1):
        yield ServerSentEvent(event="tick", id=str(i), data=EVENT_LOG[i - 1])
        await asyncio.sleep(0.5)
    yield ServerSentEvent(event="done", id=str(len(EVENT_LOG)), data={"ok": True})


# ---------- 3. POST + SSE：LLM/MCP 场景的常见形态 ----------


class Prompt(BaseModel):
    text: str


@app.post("/chat/stream", response_class=EventSourceResponse)
async def chat_stream(prompt: Prompt):
    for token in prompt.text.split():
        yield ServerSentEvent(event="token", data=token)
        await asyncio.sleep(0.2)
    # raw_data：不 JSON 编码，原样发送。OpenAI 流式结束标记就是裸的 [DONE]
    yield ServerSentEvent(event="done", raw_data="[DONE]")
