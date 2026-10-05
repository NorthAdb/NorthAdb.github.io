# 模块 3：WebSocket 双向通信

> 3 课 · 实验 v4 · 目标：掌握双向长连接的协议本质与多连接管理

> 配图：WebSocket 握手与生命周期 [diagrams/03-websocket-handshake.html](../diagrams/03-websocket-handshake.html)

---

## L3.1 握手与生命周期：一条连接的"变身"

### 目标
描述 WebSocket 从 HTTP 到双向帧通道的全过程；说出 ping/pong 与关闭码的作用。

### 概念

WebSocket 复用 HTTP 的"入口"，但换掉"内容"：

```
① 客户端发 HTTP 请求（带Upgrade 头）
   GET /ws/chat HTTP/1.1
   Upgrade: websocket            ← 我请求变身
   Connection: Upgrade
   Sec-WebSocket-Key: x3JJHMbDL1EzLkh9GBhXDw==

② 服务端同意（101 Switching Protocols）
   HTTP/1.1 101 Switching Protocols
   Upgrade: websocket

③ 从此这条 TCP 连接上跑的不再是 HTTP 报文，而是 WebSocket 帧：
   客户端 → 服务端 → 服务端 → 客户端 → …（任意交错）
```

生命周期状态机（对照架构图 03）：`Connecting → 握手 → Open →（消息往返 + ping/pong 保活）→ Closing（带状态码）→ Closed`。
- **ping/pong**：协议层心跳。任何一端可发 ping，对方必须回 pong——用于探活（应用层也有心跳，两者不同层）。
- **关闭码**：1000 正常关闭、1001 对端离开（页面关闭）、1011 服务器内部错误……异常排查时先看它。

浏览器端 API：
```javascript
const ws = new WebSocket("ws://127.0.0.1:8804/ws/chat");
ws.onopen = () => ws.send(JSON.stringify({name: "A", text: "hi"}));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.onclose = (e) => console.log(e.code, e.reason);
```

### 自测
1. 101 之后，这条连接上还能发普通 HTTP 请求吗？（不能——协议已换）
2. `ws://` 与 `https://` 对应的安全版本是什么？（`wss://`——生产必用）

---

## L3.2 FastAPI WebSocket 实战：echo → 聊天室

### 目标
跑通 v4；理解 accept / 收发循环 / WebSocketDisconnect 三要素。

### 实操

```bash
python -m uvicorn v4_websocket.app:app --port 8804 --reload
```
1. 双击打开 labs/v4_websocket/chat.html，**开两个标签页**互发消息；
2. F12 → Network → 选 ws/chat → **Messages 面板**：绿↓收到的帧、橙↑发出的帧——"双向"第一次变得可见；
3. 关掉一个标签页，观察另一个页面的"离开"广播；
4. 自动化验证：`python v4_websocket/ws_client.py`。

### 代码流程讲解（v4_websocket/app.py）

1. `@app.websocket("/ws/echo")`：注册的不是 HTTP 路由而是 WS 端点。`await ws.accept()` 完成 101 握手——注意它**不是自动的**，这给了你"拒绝连接"（403 语义）的机会。
2. `receive_text()` 会挂起等待下一帧——协程挂起期间事件循环服务其他连接（L1.1 的价值兑现）。`send_text/send_json` 随时可用，两个方向各自独立。
3. `except WebSocketDisconnect`：客户端断开的**唯一正常出口**。聊天室版在断开时把连接从登记簿移除并广播"离开"。

---

## L3.3 ConnectionManager 与广播：多连接的工程问题

### 目标
实现并解释 ConnectionManager；能回答"什么场景必须 WS"。

### 代码流程讲解（ConnectionManager）

```python
class ConnectionManager:
    def __init__(self): self.active: list[WebSocket] = []
    async def connect(self, ws): await ws.accept(); self.active.append(ws)
    def disconnect(self, ws): ...
    async def broadcast(self, message):
        for ws in list(self.active):        # ① 快照遍历
            try: await ws.send_json(message)
            except Exception: self.disconnect(ws)   # ② 死连接就地清理
```
两个细节值得多想一分钟：
- ① `list(...)` 快照：广播过程中可能有连接断开导致列表变化，边遍历边改列表是经典 bug。
- ② `await send_json` 是**串行**的：某个客户端收得慢会拖慢整个广播循环。生产解法是"每连接一个发送队列 + 后台发送任务"（把 L1.1 的 Queue 用起来）——这个模式在 v7 的订阅者队列里重现。

### SSE vs WebSocket 选型判断（本模块最重要的产出）

```
只需要服务器不断告诉客户端发生了什么？
    → SSE（实现简单、自动重连、天然过代理、文本事件够用）
        LLM token 流、RAG 进度、任务日志、通知推送

需要客户端随时往回说话？
    → WebSocket（双向、低延迟、二进制帧）
        暂停/取消/审批、协同编辑、语音、实时游戏

两者都要？→ 混合（M4 的毕业实验就是）：
    SSE 负责直播（Agent → UI），WS 负责遥控（UI → Agent）
```
真实世界印证：OpenAI API 和 Dify 的输出通道都是 SSE；需要人工中断/审批的 Agent UI（如 CopilotKit/AG-UI 生态）则加一条控制通道。

### 自测（见 labs/v4_websocket/README.md）
1. 为什么广播前要快照列表？
2. v4 的广播串行 await 有什么隐患？怎么解？
3. 举两个"必须 WS"和两个"SSE 就够"的场景。

### 延伸
- 多 Worker 场景下连接表放进程内存的局限 → M5 的 Redis Pub/Sub。
