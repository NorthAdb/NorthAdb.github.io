"""实验 v4：WebSocket——echo、聊天室与 ConnectionManager。

启动：python -m uvicorn v4_websocket.app:app --port 8804 --reload
观察：
  浏览器打开同目录 chat.html（或 python -m http.server 8804 后访问
  http://127.0.0.1:8804/chat.html），开两个标签页互发消息看广播。
自动化验证：python v4_websocket/ws_client.py   （需要服务已启动）

与 SSE 的本质区别：同一个连接上，receive_* 和 send_* 可以交替进行——双向。
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="v4 WebSocket")


# ---------- 1. 最小回声：证明"双向"存在 ----------


@app.websocket("/ws/echo")
async def ws_echo(ws: WebSocket) -> None:
    """生命周期三步：accept() 握手完成 → 收发循环 → 断开。

    对比 SSE：SSE 只有 send 方向；这里 receive 与 send 随意交错。
    """
    await ws.accept()  # 完成 HTTP Upgrade 握手，连接升级为 WebSocket
    try:
        while True:
            text = await ws.receive_text()  # 阻塞等待下一条消息
            await ws.send_text(f"echo: {text}")
    except WebSocketDisconnect:  # 客户端关页面/断网 → 这里是唯一出口
        print("echo 客户端断开")


# ---------- 2. ConnectionManager：多连接的登记簿 ----------


class ConnectionManager:
    """FastAPI 官方教程同款模式：所有活跃连接的登记、单发、广播。"""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def send_personal(self, message: dict, ws: WebSocket) -> None:
        await ws.send_json(message)

    async def broadcast(self, message: dict) -> None:
        # 快照遍历：广播过程中可能有连接断开导致列表变化
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)  # 死连接就地清理


manager = ConnectionManager()


# ---------- 3. 聊天室：广播模型 ----------


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket) -> None:
    await manager.connect(ws)
    await manager.broadcast({"type": "system", "text": "一位新朋友加入了"})
    try:
        while True:
            data = await ws.receive_json()  # {"name": "...", "text": "..."}
            await manager.broadcast(
                {"type": "chat", "from": data.get("name", "匿名"), "text": data.get("text", "")}
            )
    except WebSocketDisconnect:
        manager.disconnect(ws)
        await manager.broadcast({"type": "system", "text": "一位朋友离开了"})
