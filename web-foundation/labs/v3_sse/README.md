# v3 SSE：三个版本的对照实验

| 文件 | 定位 | 什么时候用 |
|---|---|---|
| `v3a_raw_sse.py` | 手拼 SSE 报文（`StreamingResponse` + 字符串） | **只为了理解协议**，生产禁用 |
| `v3b_fastapi_sse.py` | FastAPI 原生 `fastapi.sse` | 新项目首选，本课程默认 |
| `v3c_sse_starlette.py` | 第三方 `sse-starlette` | 存量项目/需要更多控制（如 ping 间隔） |

三个服务共用 8803 端口，**同一时间只启动一个**。

## 启动与观察

```bash
# A：裸格式
python -m uvicorn v3_sse.v3a_raw_sse:app --port 8803 --reload
curl -N -i http://127.0.0.1:8803/events
# 观察 body：
#   : heartbeat-comment        ← 注释行（客户端忽略，可当心跳）
#   retry: 3000                ← 教浏览器断线后 3 秒重连
#   event: count / id: 1 / data: {...}  ← 一条命名事件
#   （空行）                    ← 事件结束的标志

# B：原生（先 Ctrl+C 停掉 A）
python -m uvicorn v3_sse.v3b_fastapi_sse:app --port 8803 --reload
curl -N http://127.0.0.1:8803/events
curl -N -H "Last-Event-ID: 3" http://127.0.0.1:8803/resumable   # 从 4 号开始补发
curl -N -X POST http://127.0.0.1:8803/chat/stream -H "Content-Type: application/json" -d '{"text": "hello fastapi sse"}'

# C：sse-starlette（同样先停掉上一个）
python -m uvicorn v3_sse.v3c_sse_starlette:app --port 8803 --reload
curl -N http://127.0.0.1:8803/events
# 等 5 秒以上，观察 ": ping" 心跳行
```

## 浏览器实测（必做）

双击打开 `sse_client.html`（或 `python -m http.server` 后访问），
填入 `http://127.0.0.1:8803/events` → Connect：

> 为什么双击就能用？file:// 页面连 SSE 端点是**跨源请求**（Origin: null），EventSource 受 CORS 约束。
> 三个实验服务都加了 `CORSMiddleware(allow_origins=["*"])` 放行——生产服务请改成前端站点白名单，别用 `*`。
> 对照实验：把中间件注释掉重启，页面会 onerror 且 readyState=2，这就是"跨域被浏览器拦下"的现场。

1. 日志里出现 `readyState: 1 (OPEN)`，`count` 事件逐条到达；
2. **断线重连实验**：把服务端 Ctrl+C 停掉 → 日志显示 `readyState: 0 (CONNECTING)`——浏览器在自动重连；重启服务端 → 流自动恢复；
3. 连 `resumable` 端点重复实验 → 重连后带 `Last-Event-ID` 补发，日志里能看到 `lastEventId`。

## 代码流程讲解

- **v3a**：`sse_format()` 就是协议本身——字段行 + 空行。`media_type="text/event-stream"` 让浏览器启用 EventSource 语义。手写一遍后，v3b 里框架帮你做的事就全部"看得见"了。
- **v3b**：`ServerSentEvent(event=..., id=..., data=...)` 对象化同样的字段；`raw_data="[DONE]"` 对齐 OpenAI 流式结束标记；`Last-Event-ID` 用 `Header()` 声明即可拿到浏览器自动回传的续传位点。
- **v3c**：API 形态几乎一样（dict 即事件），区别是 `ping=5` 显式配置心跳——对应 v3b 里框架内置的 15 秒心跳。

## 自测问题

1. SSE 报文里"一条事件结束"的标志是什么？漏了会怎样？
2. 浏览器把 `id` 字段存成了什么？重连时放在哪个请求头里？
3. `event: token` 的事件，`EventSource.onmessage` 能收到吗？该用什么收？
4. 心跳为什么用注释行（`: ping`）而不是一条真事件？
5. 为什么 LLM 服务商（OpenAI/MCP）都选 SSE 而不是让客户端轮询？

## 延伸

- MDN: Using server-sent events；FastAPI SSE 教程；sse-starlette README（心跳/超时参数）
