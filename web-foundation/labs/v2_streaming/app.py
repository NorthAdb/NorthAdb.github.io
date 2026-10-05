"""实验 v2：HTTP Streaming——从"攒够再回"到"边产边发"。

启动：python -m uvicorn v2_streaming.app:app --port 8802 --reload
观察（关键！）：
  curl -N -i http://127.0.0.1:8802/slow     # 等 3 秒，一次性出现
  curl -N -i http://127.0.0.1:8802/stream   # 每隔 0.5 秒蹦出一个数字
  curl -N http://127.0.0.1:8802/llm-sim     # 模拟 LLM 逐字输出

-N 禁用 curl 的输出缓冲，否则你看到的还是"攒一起"的假象。
"""

import asyncio
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="v2 HTTP Streaming")


@app.get("/slow")
async def slow() -> dict:
    """普通响应：函数 return 的那一刻，响应体才完整存在。

    客户端在这 3 秒里什么都收不到——这正是 LLM 问答"转圈圈"的体验问题。
    """
    await asyncio.sleep(3)
    return {"message": "整整等了 3 秒才一次性返回"}


async def number_stream(count: int = 10, interval: float = 0.5) -> AsyncIterator[str]:
    """async generator：每次 yield 一个片段，StreamingResponse 立刻把它发给客户端。

    时间线：
      yield "1" → 网络发出 chunk 1 → await sleep → yield "2" → chunk 2 → ...
    """
    for i in range(1, count + 1):
        yield f"{i}\n"
        await asyncio.sleep(interval)


@app.get("/stream")
async def stream() -> StreamingResponse:
    # StreamingResponse 接收 async generator，并负责把每个 yield 变成一个 HTTP chunk。
    return StreamingResponse(number_stream(), media_type="text/plain")


@app.get("/llm-sim")
async def llm_sim() -> StreamingResponse:
    """模拟 LLM token 流：字节层面已经和 ChatGPT 打字机效果同构，只差 SSE 的事件封装。"""

    async def tokens() -> AsyncIterator[str]:
        answer = "RAG 是一种检索增强生成技术，先查资料，再回答。"
        for ch in answer:
            yield ch
            await asyncio.sleep(0.08)

    return StreamingResponse(tokens(), media_type="text/plain; charset=utf-8")
