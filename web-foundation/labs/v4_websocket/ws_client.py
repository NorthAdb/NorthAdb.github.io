"""自动化验证脚本：对 v4 服务做 echo 与聊天室广播测试。

先启动服务：python -m uvicorn v4_websocket.app:app --port 8804
再运行：    python v4_websocket/ws_client.py
"""

import asyncio
import json
import sys

import websockets  # uvicorn[standard] 自带；独立安装：pip install websockets

# Windows 管道/重定向下 stdout 退回 GBK：print("✔") 会抛 UnicodeEncodeError 中断脚本
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

BASE = "ws://127.0.0.1:8804"


async def test_echo() -> None:
    async with websockets.connect(f"{BASE}/ws/echo") as ws:
        await ws.send("你好，WebSocket")
        reply = await asyncio.wait_for(ws.recv(), timeout=5)
        print(f"echo 测试：{reply}")
        assert reply == "echo: 你好，WebSocket"


async def test_chat_broadcast() -> None:
    async with websockets.connect(f"{BASE}/ws/chat") as a, websockets.connect(
        f"{BASE}/ws/chat"
    ) as b:
        await asyncio.sleep(0.5)  # 让两条"新朋友加入"的系统消息先到达
        # 排空各自积压的系统消息
        for _ in range(2):
            try:
                await asyncio.wait_for(a.recv(), timeout=0.5)
                await asyncio.wait_for(b.recv(), timeout=0.5)
            except TimeoutError:
                break
        await a.send('{"name": "A", "text": "大家好"}')
        msg_a = json.loads(await asyncio.wait_for(a.recv(), timeout=5))
        msg_b = json.loads(await asyncio.wait_for(b.recv(), timeout=5))
        print(f"A 收到: {msg_a}")
        print(f"B 收到: {msg_b}")
        assert msg_b["text"] == "大家好"


if __name__ == "__main__":
    asyncio.run(test_echo())
    asyncio.run(test_chat_broadcast())
    print("全部通过 ✔")
