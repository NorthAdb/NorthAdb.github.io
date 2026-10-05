"""实验 v3c：sse-starlette——原生 SSE 出现前的事实标准（大量存量项目在用）。

启动：python -m uvicorn v3_sse.v3c_sse_starlette:app --port 8803 --reload
观察：
  curl -N http://127.0.0.1:8803/events
  # 空闲超过 5 秒，你会看到一条 ": ping" 注释行——这就是库替你发的心跳。
  # 对比 v3b：fastapi.sse 内置同样的机制（15 秒间隔），只是不用你配置。

为什么还要认识它：Dify、LibreChat 等开源项目大量使用 sse-starlette。
读它们源码前，先在这里认识它的 API。
"""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette import EventSourceResponse

app = FastAPI(title="v3c sse-starlette")

# 同 v3a/v3b：放行 file:// 的 sse_client.html（跨源实验页）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/events")
async def events() -> EventSourceResponse:
    async def gen() -> AsyncIterator[dict]:
        for i in range(1, 4):
            # sse-starlette 接受 dict：event/id/retry/data 等键会被转成对应字段。
            # 两个坑（库之间的微妙差异，读源码前必知）：
            #   1. id 必须是 str（int 会直接抛 TypeError）
            #   2. data 传 dict 时它用 str() 而非 json.dumps（线上是 Python repr！），
            #      所以这里自己 json.dumps 成字符串，跨库行为才一致
            yield {
                "event": "count",
                "id": str(i),
                "data": json.dumps({"n": i}, ensure_ascii=False),
            }
            await asyncio.sleep(1)

        yield {"event": "done", "data": "bye"}
        # 之后再无输出：ping=5 表示空闲 5 秒发一条 ": ping" 心跳，防止代理掐掉空闲连接
        await asyncio.sleep(12)

    return EventSourceResponse(gen(), ping=5)
