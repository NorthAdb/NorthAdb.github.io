# v4 WebSocket：echo → 聊天室 → ConnectionManager

目标：建立双向长连接的心智模型，掌握连接管理与广播。

## 启动与观察

```bash
python -m uvicorn v4_websocket.app:app --port 8804 --reload
```

1. 浏览器打开 `chat.html`（直接双击即可，或 `python -m http.server 8804` 后访问 `http://127.0.0.1:8804/chat.html`）。
2. **开两个标签页**，取名 A / B 互发消息 → 双方都能收到，包括"新朋友加入"的系统广播。
3. F12 → Network → 选中 `ws/chat` → Messages 面板：**绿色箭头 ↓ 是收到的帧，橙色 ↑ 是发出的帧**。这就是"双向"的实体。
4. 关掉一个标签页 → 另一个页面立刻收到"离开"广播。
5. 自动化验证：`python v4_websocket/ws_client.py`（保持服务运行）。

## 代码流程讲解（app.py）

1. **`@app.websocket("/ws/echo")`**：不是 HTTP 路由，是 WS 端点。连接进来时还是 HTTP，
   `await ws.accept()` 才完成 `101 Switching Protocols` 握手——从此这条 TCP 连接上跑的是 WebSocket 帧，不再是 HTTP 报文。
2. **收发循环**：`receive_text()` 挂起等待下一帧；`send_text()` 发一帧。两个方向各自独立、可任意交错——这是它与 SSE（只能服务器说）的本质区别。
3. **`WebSocketDisconnect`**：客户端关闭的唯一正常出口。不做 try/except 的话，断连异常会向上抛，产生错误日志。
4. **`ConnectionManager`**：多连接的登记簿。`connect` 登记、`broadcast` 遍历快照逐个 `send_json`、失败连接就地清理。
   注意广播是**串行 await** 的——一个慢连接会拖慢整个广播循环（模块 5 讲解法：每连接发送队列 + 后台任务）。

## 自测问题

1. `101 Switching Protocols` 出现在什么时刻？握手前后这条连接上分别跑什么协议？
2. 为什么广播前要对 `self.active` 做 `list(...)` 快照？
3. 两个客户端同时发消息，服务端怎么保证不乱？（提示：每个连接是独立的协程，事件循环调度）
4. 什么场景必须 WebSocket、SSE 做不了？举两个。

## 延伸

- FastAPI 官方 WebSockets 教程；MDN WebSocket API；下一模块把"聊天的 text"换成"Agent 的事件与控制指令"。
