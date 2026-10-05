"""n1 的极简后端：专门用来观察"穿过 Nginx 之后"流会变成什么样。

- /sse       ：10 个 SSE 事件，每 0.5 秒一个（共约 5 秒）——缓冲实验的主角
- /slow      ：3 秒后返回一个 JSON——对照组
- /ws/echo   ：WebSocket 回声——验证 Upgrade 头透传

启动：python -m uvicorn n1_nginx_proxy.app:app --port 8807
"""

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.sse import EventSourceResponse, ServerSentEvent

app = FastAPI(title="n1 · Nginx 实验后端")

# 每个 SSE 事件填充到 ~600 字节（模拟 LLM 真实的大 JSON 块）。
# 这让"缓冲 on"的破坏可见：10 个事件 ≈ 6KB，超过 nginx 默认 8KB 缓冲前
# 会被整块攒住；缓冲 off 时则逐个转发。小事件（几十字节）两者差异不明显。
PAD = ": " + ("llm-chunk-padding-" * 30)


@app.get("/sse")
async def sse():
    # 前 3 个事件每 0.3s 一个 → 静默 4 秒（模拟 LLM 思考）→ 再每 0.3s 发完。
    # 静默期是 read_timeout 事故的触发窗口：事故配置（2s）会在这里掐断连接。
    for i in range(1, 4):
        yield ServerSentEvent(event="tick", id=str(i), data={"n": i}, comment=PAD)
        await asyncio.sleep(0.3)
    await asyncio.sleep(4)  # ← 静默 4 秒：LLM 思考中的真实形态
    for i in range(4, 11):
        yield ServerSentEvent(event="tick", id=str(i), data={"n": i}, comment=PAD)
        await asyncio.sleep(0.3)


@app.get("/slow")
async def slow() -> dict:
    await asyncio.sleep(3)
    return {"message": "3 秒后一次性返回"}


@app.websocket("/ws/echo")
async def ws_echo(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            await ws.send_text(await ws.receive_text())
    except WebSocketDisconnect:
        pass
