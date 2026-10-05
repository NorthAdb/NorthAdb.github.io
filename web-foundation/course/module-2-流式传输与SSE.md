# 模块 2：流式传输与 SSE

> 5 课 · 实验 v2、v3a/v3b/v3c · 目标：从"响应可以分块"到"生产级 SSE + 断线续传"，这是全课程权重最高的模块

> 配图：SSE 连接生命周期 [diagrams/02-sse-lifecycle.html](../diagrams/02-sse-lifecycle.html)

---

## L2.1 ASGI 分层：请求从浏览器到你的函数经过谁

### 目标
不查资料画出五层调用链，说出每层职责。

### 概念

```
浏览器
   │  HTTP / WebSocket
   ▼
Uvicorn        （ASGI 服务器：管 TCP 连接、解析字节流、跑事件循环）
   │  ASGI 接口（scope / receive / send 三个 callable 的约定）
   ▼
Starlette      （Web 工具箱：路由、请求/响应对象、中间件、WebSocket/Streaming 实现）
   │
   ▼
FastAPI        （开发体验层：类型注解→校验、依赖注入、OpenAPI……基于 Starlette）
   │
   ▼
你的端点函数
```

- **ASGI** 是"服务器 ↔ 应用"之间的**接口标准**（如同 WSGI 的异步版）。它规定了服务器把请求翻译成什么字典、应用怎么逐块送回响应。有了这个标准，服务器（uvicorn/hypercorn）和框架（FastAPI/Starlette/Django）才能自由组合。
- 记忆锚点：**Uvicorn 管"字节"，Starlette 管"Web"，FastAPI 管"你"**。

为什么这门课要懂这个：SSE 和 WebSocket 的能力**不是 FastAPI 发明的**，是 Starlette/ASGI 层提供的"持续写响应"能力；FastAPI 只是给你一个体面的入口。

### 自测
1. `uvicorn app:app` 中两个 `app` 分别指什么？
2. SSE 的 `text/event-stream` 响应头是谁写进 socket 的——FastAPI、Starlette 还是 Uvicorn？（答：FastAPI/Starlette 组装响应对象，Uvicorn 编码发送——分层协作）

---

## L2.2 StreamingResponse：yield 如何变成 HTTP chunk

### 目标
跑通 v2；解释 `async generator → StreamingResponse → chunked encoding` 的因果链。

### 概念

普通响应：函数 `return` 时响应体才完整存在 → 客户端干等。
流式响应：`transfer-encoding: chunked`——响应体被切成一个个 chunk，**每块发完不关连接，继续发下一块**，最后发一个长度为 0 的 chunk 表示结束。这与 Keep-Alive（L1.3）是同一思想的延伸：连接不必和"一次完整响应"绑定。

### 实操：实验 v2

```bash
python -m uvicorn v2_streaming.app:app --port 8802 --reload
curl -N -i http://127.0.0.1:8802/slow      # 对照组：3 秒后一次到齐
curl -N -i http://127.0.0.1:8802/stream    # 每 0.5s 蹦一个数字
```
对照实验：去掉 `-N`（curl 客户端缓冲）→ 假装不流式了。**流式系统中每一环（客户端、代理）都可能"攒货"**——这个概念在 L5.2 变成 Nginx 的 `proxy_buffering off`。

### 代码流程讲解（v2_streaming/app.py）

1. `number_stream()` 是 async generator：`yield f"{i}\n"` 表示"这块数据好了"，`await asyncio.sleep` 让出事件循环。
2. `StreamingResponse(number_stream())` 的运行时行为：
   先发响应头（无 content-length，有 transfer-encoding: chunked）→ 驱动 generator → 每个 yield 编码为一个 chunk 写入 socket → generator 结束（StopAsyncIteration）→ 发 0 长度终止 chunk。
3. `/llm-sim` 逐字吐答案：**字节层面已经与 ChatGPT 打字机同构**，只差"事件语义"——这正是 L2.3 SSE 的内容。

### 自测
见 labs/v2_streaming/README.md。重点第 3 题：generator 里跑 10 秒纯 CPU 循环会怎样？（答：事件循环被卡住，所有连接一起遭殃——再次呼应 L1.1）

---

## L2.3 SSE 协议格式精讲：手写一遍报文

### 目标
能在纸上写出合法 SSE 报文；解释 event/id/retry/注释行各自的作用。

### 概念

SSE = 普通流式响应 + 两条约定：
1. **格式约定**（响应体怎么写）：
```
: 这是以冒号开头的注释行，客户端忽略（常用作心跳）      ← 注释
retry: 3000                                          ← 教浏览器：断线后 3s 重连
id: 42                                               ← 事件编号，浏览器记住它
event: token                                         ← 事件名（缺省为 message）
data: {"text": "检"}                                 ← 载荷（多行=多个 data 行）
                                                     ← 空行 = 一条事件结束（漏了不派发！）
```
2. **客户端约定**（浏览器 EventSource 的行为）：
   - 收到 `id` → 存为 lastEventId；
   - 连接断了 → 自动重连，并带上请求头 `Last-Event-ID: 42`；
   - `event: token` 的事件要用 `addEventListener("token", ...)` 收，`onmessage` 只收无名事件。

### 实操：实验 v3a

```bash
python -m uvicorn v3_sse.v3a_raw_sse:app --port 8803 --reload
curl -N -i http://127.0.0.1:8803/events     # 对照 v3a 的 sse_format() 看原始字节
```
浏览器打开 labs/v3_sse/sse_client.html → 连接 → 观察命名事件如何被 addEventListener 收到。

### 代码流程讲解（v3a_raw_sse.py）
`sse_format()` 就是协议本身：字段行 + 空行。手写一遍的意义——此后 v3b 里框架帮你做的每件事你都"看得见"（Content-Type、no-cache、X-Accel-Buffering、心跳）。**这是本课程"手写只为理解"原则的典型应用**。

> 💡 互动课：[lessons/0002 SSE 格式实验室](../lessons/0002-sse-format-lab.html)——可编辑的报文 + 实时解析成事件卡片，把"空行才派发"这类规则亲手验证一遍。

---

## L2.4 生产级 SSE：fastapi.sse 原生支持

### 目标
用原生 API 重写 v3a 的功能；实现断线续传；掌握 POST+SSE。

### 概念与 API

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.get("/events", response_class=EventSourceResponse)
async def events():                    # 必须是 async generator（见下方"踩坑实录"）
    yield ServerSentEvent(event="token", id="1", data={"text": "检"})
```
框架自动处理：`content-type: text/event-stream`、`cache-control: no-cache`、`x-accel-buffering: no`（告诉 Nginx 别缓冲）、**15 秒无消息自动发 comment 心跳**（防止代理把空闲连接掐了）。

**踩坑实录**（2026-09 实测 fastapi 0.141.1，已写入 learning-records/0002）：
1. 端点函数**必须自身是 async generator**（函数体有 yield）。`return EventSourceResponse(gen())` 会在请求时抛 `'coroutine' object is not iterable`。
2. 返回注解 `AsyncIterable[ServerSentEvent]` 只能配 yield 风格。
3. 404 等错误语义必须放进 **Depends 依赖**（响应开始前执行）；在 generator 里 raise 只会把已发出的 200 流中途掐断。

### 断线续传（Last-Event-ID）——本课高潮

浏览器重连时自动带 `Last-Event-ID` 头。服务端"补发错过的事件"：
```python
@app.get("/resumable", response_class=EventSourceResponse)
async def resumable(last_event_id: Annotated[str | None, Header()] = None):
    start = int(last_event_id) + 1 if last_event_id else 1
    for i in range(start, len(EVENT_LOG) + 1):
        yield ServerSentEvent(event="tick", id=str(i), data=EVENT_LOG[i - 1])
```
> 对照架构图 02（SSE 生命周期）：连接 → 事件流（带 id）→ 断开 → 自动重连（带 Last-Event-ID）→ 从断点续传 → done。

**为什么这直接关联 Agent**：Agent 跑 10 分钟、用户进电梯断网 30 秒，重连后前端要能"补课"。补课的依据就是事件日志 + 单调递增的 seq（M4 里叫 seq，这里叫 id，同一件事）。

### POST + SSE
`EventSource` 浏览器 API 只支持 GET，但 SSE 协议本身配任何方法都行。POST+SSE 是 **LLM API（OpenAI）与 MCP Streamable HTTP** 的标准形态——v3b 的 `/chat/stream` 就是它的雏形。

---

## L2.5 sse-starlette 与生态对照

### 目标
认识存量项目的标准库；理解"库之间微妙差异"为什么要读源码。

### 实操：实验 v3c

```bash
python -m uvicorn v3_sse.v3c_sse_starlette:app --port 8803 --reload
curl -N http://127.0.0.1:8803/events    # 空闲 5 秒后看 ": ping" 心跳行
```

### 实测发现的两个库差异（v3c 注释里也写了）
1. sse-starlette 的 `id` 必须是 **str**（int 直接 TypeError）；
2. 它的 `data` 传 dict 时用 `str()` 而不是 JSON 编码——线上会出现 `data: {'n': 1}` 这种 Python repr！要自己 `json.dumps`。
> 结论：**同类库的行为差异要在"字节层"验证，不能想当然**。这正是本课程坚持 curl 看原始格式的原因。

### 选型结论（记住这张表）

| 方案 | 什么时候用 |
|---|---|
| 手拼 StreamingResponse（v3a） | 只用于理解协议 |
| fastapi.sse（v3b） | 新项目默认；内置心跳；与框架集成最好 |
| sse-starlette（v3c） | 存量项目、需要自定义 ping 间隔/超时；Dify、LibreChat 在用 |

### 自测（本模块总检）
1. chunked 和 SSE 的区别？（流式字节 vs 结构化事件流）
2. 心跳为什么用注释行而不是一条真事件？
3. 浏览器怎么知道该从哪里续传？服务端怎么知道？
4. 为什么 OpenAI/MCP 都选 POST+SSE 而不是 GET+SSE？

### 延伸
- WHATWG 规范的 SSE 章节只在你需要裁定"为什么"时读；MDN 的 Server-sent events 适合复习。
