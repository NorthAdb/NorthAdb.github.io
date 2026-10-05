"""实验 v3a：手写 SSE 裸格式——为了理解协议，自己拼一次报文（生产别这么用）。

启动：python -m uvicorn v3_sse.v3a_raw_sse:app --port 8803 --reload
观察：
  curl -N -i http://127.0.0.1:8803/events
对照 v2：响应头 media_type 变成了 text/event-stream，body 不再是随意文本，
         而是"字段名: 值 + 空行"的固定格式。浏览器 EventSource 只认这种格式。
"""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

app = FastAPI(title="v3a 手写 SSE")

# sse_client.html 允许双击以 file:// 打开——那是跨源请求（Origin: null），
# EventSource 走 CORS，所以实验服务显式放行。生产服务不要配 "*"，要白名单。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse_format(
    data: str = "",
    event: str | None = None,
    id_: str | None = None,
    retry: int | None = None,
    comment: str | None = None,
) -> str:
    """把字段拼成 SSE 报文。规则（WHATWG HTML 规范）：

    - 每个字段一行：`field: value`
    - 一条事件 = 若干字段行 + 一个空行（\\n\\n）
    - `data` 是事件载荷；`event` 是事件名（浏览器用 addEventListener 收）；缺省为 message
    - `id` 会成为浏览器 lastEventId，断线重连时随 Last-Event-ID 头发回服务端
    - `retry` 告诉浏览器：断线后等多少毫秒再重连
    - 以 `:` 开头的行是注释，客户端忽略——常用来做心跳
    - data 需要多行时，写多个 data 行（这里简化为单行）
    """
    lines: list[str] = []
    if comment is not None:
        lines.append(f": {comment}")
    if retry is not None:
        lines.append(f"retry: {retry}")
    if id_ is not None:
        lines.append(f"id: {id_}")
    if event is not None:
        lines.append(f"event: {event}")
    for dline in data.splitlines() or [""]:
        lines.append(f"data: {dline}")
    return "\n".join(lines) + "\n\n"  # 空行 = 事件结束，少写浏览器就不派发


@app.get("/events")
async def events() -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        # 第一条：不带 event 名 → 浏览器当作 message 事件；retry=3000 教会浏览器重连节奏
        yield sse_format(data="连接成功", retry=3000, comment="heartbeat-comment")

        for i in range(1, 6):
            yield sse_format(
                event="count",
                id_=str(i),
                data=json.dumps({"n": i}, ensure_ascii=False),
            )
            await asyncio.sleep(1)

        yield sse_format(event="done", data="finished")

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",  # SSE 的身份证：浏览器靠它判定这是事件流
        headers={
            "Cache-Control": "no-cache",      # 事件流绝不能被缓存
            "X-Accel-Buffering": "no",        # 告诉 Nginx：别攒着，来了就转发
        },
    )
