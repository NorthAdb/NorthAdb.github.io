# SSE、WebSocket 与 FastAPI 完整学习路线

> 目标：系统理解 **HTTP、FastAPI、ASGI、Streaming、SSE、WebSocket**，并最终将它们串联到 **LLM Streaming、RAG、Agent Server、Agent UI** 中。

---

# 1. 整体认知

这几个概念不要割裂学习，可以理解成一条技术链：

```text
Python Async
     ↓
    HTTP
     ↓
  FastAPI
     ↓
   ASGI
     ↓
 Streaming
    ├──────────────┐
    ↓              ↓
   SSE         WebSocket
    │              │
服务器推送       双向通信
    │              │
    └──────┬───────┘
           ↓
      LLM Streaming
           ↓
       Agent Events
           ↓
      Agent Server
           ↓
        Agent UI
```

其中：

- **FastAPI**：Python Web 服务开发框架
- **HTTP**：Web 通信基础协议
- **SSE**：基于 HTTP 的服务器 → 客户端单向实时推送
- **WebSocket**：客户端 ↔ 服务器双向实时通信
- **ASGI**：Python 异步 Web Server 与 Web Application 之间的接口标准
- **Uvicorn**：常见的 ASGI Server
- **Streaming**：将响应分块持续发送，而不是等全部生成完成再返回

---

# 2. FastAPI、SSE、WebSocket 的关系

## 2.1 FastAPI 是框架

FastAPI 解决的问题是：

> 如何用 Python 构建一个现代 Web API 服务。

例如：

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
async def hello():
    return {"message": "hello"}
```

客户端：

```text
GET /hello
```

服务器：

```json
{
  "message": "hello"
}
```

FastAPI 常见能力：

```text
路由
参数解析
JSON
Pydantic 数据校验
依赖注入
Middleware
异常处理
认证
Streaming
SSE
WebSocket
OpenAPI
```

## 2.2 SSE 与 WebSocket 是通信机制

它们不是 FastAPI 的替代品。

```text
FastAPI
│
├── 普通 HTTP API
├── Streaming
├── SSE
└── WebSocket
```

FastAPI 负责提供服务端的开发框架，而 SSE / WebSocket 解决的是不同的实时通信需求。

---

# 3. SSE

## 3.1 SSE 是什么

SSE：

```text
Server-Sent Events
```

核心模型：

```text
Client ───── HTTP Request ─────► Server
Client ◄──── 持久 HTTP 连接 ──── Server
                        ▲
                        │
                   持续推送事件
```

核心特点：

```text
Server → Client
单向
长连接
基于 HTTP
事件流
```

## 3.2 SSE 适合什么

典型场景：

```text
LLM Token Streaming
Agent 状态更新
Agent Tool Call 日志
RAG 检索进度
文件处理进度
后台任务进度
实时通知
监控数据
```

例如：

```text
event: status
data: 正在读取 PDF

event: status
data: 正在进行 RAG 检索

event: token
data: 根据文档内容

event: token
data: 可以发现

event: done
data: 完成
```

## 3.3 浏览器端 SSE

```javascript
const source = new EventSource("/events")

source.onmessage = (event) => {
    console.log(event.data)
}
```

服务器持续发送：

```text
data: hello

data: world

data: done
```

## 3.4 SSE 的核心概念

```text
t​ext/event-stream
event
data
id
retry
heartbeat
disconnect
reconnect
```

重点理解：

```text
浏览器建立 SSE 连接
       ↓
服务器保持连接
       ↓
服务器持续发送 Event
       ↓
客户端实时处理
       ↓
连接结束 / 断开
       ↓
必要时重新连接
```

---

# 4. WebSocket

## 4.1 WebSocket 是什么

WebSocket 的核心：

> Client ↔ Server 双向、持续通信。

```text
Client ◄────────────────► Server
        双向长连接
```

建立连接以后：

```text
Client → Server
Server → Client
Client → Server
Server → Client
...
```

## 4.2 浏览器端 WebSocket

```javascript
const ws = new WebSocket("ws://localhost:8000/ws")

ws.onopen = () => {
    ws.send("hello")
}

ws.onmessage = (event) => {
    console.log(event.data)
}
```

## 4.3 WebSocket 适合什么

```text
在线聊天
协作编辑
实时游戏
实时控制
Agent 控制
终端控制
双向事件交互
实时状态同步
```

特别是在 Agent 中：

```text
Client → Server
    ├── pause
    ├── resume
    ├── cancel
    ├── approve_tool
    ├── reject_tool
    └── user_input

Server → Client
    ├── agent_start
    ├── tool_call
    ├── tool_result
    ├── token
    └── done
```

---

# 5. SSE 与 WebSocket 的区别

| 特性 | HTTP API | SSE | WebSocket |
|---|---|---|---|
| 通信方向 | 请求 → 响应 | Server → Client | Client ↔ Server |
| 长连接 | 通常不是 | 是 | 是 |
| 实时性 | 一般 | 高 | 高 |
| Client → Server | ✅ | ❌ | ✅ |
| Server → Client | ✅ | ✅ | ✅ |
| 浏览器 API | `fetch` | `EventSource` | `WebSocket` |
| 基于 HTTP | ✅ | ✅ | 建立阶段使用 HTTP Upgrade |
| 典型用途 | CRUD/API | Streaming/事件推送 | 实时双向交互 |
| 复杂度 | 低 | 低~中 | 中~高 |

判断模型：

```text
我只需要服务器不断告诉客户端发生了什么
                ↓
               SSE

我需要客户端和服务器双方不断交互
                ↓
           WebSocket
```

---

# 6. 为什么要先学 HTTP

先建立：

```text
HTTP Request
│
├── Method
│   ├── GET
│   ├── POST
│   ├── PUT
│   └── DELETE
│
├── URL
├── Headers
└── Body

HTTP Response
│
├── Status Code
├── Headers
└── Body
```

重点掌握：

```text
200
201
400
401
403
404
409
500
```

然后学习：

```text
Cookie
Session
Authorization
Bearer Token
CORS
Keep-Alive
Content-Type
```

同时学会浏览器：

```text
DevTools
  ↓
Network
  ↓
Request
  ↓
Response
  ↓
Headers
  ↓
Payload
```

以及：

```text
curl
httpx
Postman
```

---

# 7. Python Async 是前置基础

在 SSE、WebSocket、FastAPI 之前，应该先理解 Python 异步编程。

重点：

```text
async def
await
asyncio
Task
create_task()
gather()
Queue
Event
```

## 7.1 async / await

```python
async def foo():
    await something()
```

可以理解为：当前协程暂时等待某个异步操作完成，把执行权交给事件循环。

## 7.2 Task

```python
task = asyncio.create_task(foo())
```

允许一个异步任务并发运行。

## 7.3 Producer / Consumer

```text
Producer
   │
   ↓
 Queue
   │
   ↓
Consumer
```

这个模型对于 SSE、WebSocket、Agent Event、LLM Streaming 都很重要。

---

# 8. FastAPI 基础阶段

第一阶段先掌握普通 API。

## 8.1 Route

```python
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {
        "id": user_id
    }
```

掌握：

```text
Path Parameter
Query Parameter
Request Body
Response
```

## 8.2 Pydantic

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int
```

请求：

```json
{
  "name": "Alice",
  "age": 20
}
```

理解：

```text
JSON
 ↓
Pydantic Model
 ↓
Python Object
 ↓
Business Logic
```

## 8.3 FastAPI 基础知识树

```text
FastAPI
│
├── Route
├── Request
├── Response
├── Pydantic
├── Dependency Injection
├── Middleware
├── Exception
├── Authentication
└── OpenAPI
```

---

# 9. ASGI：真正理解 FastAPI 底层

整体：

```text
Browser / Client
       ↓
   HTTP / WS
       ↓
    Uvicorn
       ↓
      ASGI
       ↓
    FastAPI
```

再向下：

```text
FastAPI
   ↓
Starlette
   ↓
ASGI
   ↓
Uvicorn
   ↓
TCP/IP
```

各层职责：

### FastAPI

```text
API 开发体验
路由
参数
校验
依赖注入
```

### Starlette

```text
Web 基础能力
ASGI
HTTP
WebSocket
Middleware
Streaming
```

### Uvicorn

```text
运行 ASGI Application
处理网络连接
```

### ASGI

```text
Server ↔ Application
```

---

# 10. Streaming：SSE 前的关键过渡

普通 HTTP：

```text
Request
   ↓
等待
   ↓
完整结果
   ↓
Response
```

Streaming：

```text
Request
   ↓
Chunk 1
   ↓
Chunk 2
   ↓
Chunk 3
   ↓
Chunk 4
   ↓
End
```

## 10.1 FastAPI StreamingResponse

```python
import asyncio
from fastapi.responses import StreamingResponse

async def generate():
    for i in range(10):
        yield f"chunk-{i}\n"
        await asyncio.sleep(1)

@app.get("/stream")
async def stream():
    return StreamingResponse(generate())
```

理解：

```text
async generator
      ↓
yield
      ↓
StreamingResponse
      ↓
HTTP Chunk
      ↓
Browser
```

---

# 11. 从 Streaming 过渡到 SSE

SSE 可以理解为：

> 在 HTTP Streaming 的基础上定义了事件格式和客户端行为。

关系：

```text
HTTP
 ↓
HTTP Streaming
 ↓
SSE
```

因此：

```text
Streaming
= 持续传输数据

SSE
= 持续传输结构化事件
```

---

# 12. FastAPI SSE 实践

当前 FastAPI 提供专门的 SSE 接口，例如：

```python
import asyncio

from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent

app = FastAPI()

@app.get(
    "/events",
    response_class=EventSourceResponse,
)
async def events():
    for i in range(10):
        yield ServerSentEvent(
            data=f"message {i}"
        )
        await asyncio.sleep(1)
```

浏览器：

```javascript
const source = new EventSource("/events")

source.onmessage = (event) => {
    console.log(event.data)
}
```

---

# 13. SSE 学习重点

不要只停留在“会写一个 SSE”。

需要继续理解：

```text
连接建立
     ↓
事件流
     ↓
事件发送
     ↓
Heartbeat
     ↓
客户端断线
     ↓
Reconnect
     ↓
状态恢复
```

进一步思考：

```text
如果 Agent 运行 10 分钟
浏览器突然断网
重新连接之后
应该从哪里继续？
```

这就从“SSE API 使用”进入了：

> 状态管理和事件系统设计。

---

# 14. WebSocket 学习

FastAPI：

```python
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    while True:
        data = await websocket.receive_text()
        await websocket.send_text(
            f"received: {data}"
        )
```

浏览器：

```javascript
const ws = new WebSocket(
    "ws://localhost:8000/ws"
)

ws.onopen = () => {
    ws.send("hello")
}

ws.onmessage = (event) => {
    console.log(event.data)
}
```

---

# 15. WebSocket 生命周期

```text
HTTP Handshake
      ↓
Upgrade
      ↓
WebSocket Connection
      ↓
Message
      ↓
Message
      ↓
Ping / Pong
      ↓
Close
```

重点 API：

```text
accept()
receive_text()
receive_json()
receive_bytes()

send_text()
send_json()
send_bytes()

close()
```

---

# 16. Connection Manager

真正开始进入工程问题的是：多客户端如何管理。

```text
Client A ─┐
Client B ─┼──► FastAPI
Client C ─┘
```

可以抽象：

```python
class ConnectionManager:

    async def connect(self, websocket):
        ...

    def disconnect(self, websocket):
        ...

    async def send_personal_message(self, message, websocket):
        ...

    async def broadcast(self, message):
        ...
```

结构：

```text
ConnectionManager
│
├── connect
├── disconnect
├── send_personal
└── broadcast
```

---

# 17. 为什么 Redis 会出现

如果只维护：

```python
active_connections = []
```

这些连接只存在于当前 Python 进程。

例如：

```text
Nginx
  │
  ├── FastAPI Worker 1
  ├── FastAPI Worker 2
  └── FastAPI Worker 3
```

每个 Worker 都有独立的连接集合：

```text
Worker 1
  active_connections

Worker 2
  active_connections

Worker 3
  active_connections
```

因此进入：

```text
Redis Pub/Sub
```

架构变成：

```text
Client
  ↓
Nginx
  ↓
FastAPI
  ↓
Redis
  ↓
其他 Worker
```

---

# 18. LLM Streaming

普通 LLM 请求：

```text
User
 ↓
FastAPI
 ↓
LLM
 ↓
等待
 ↓
完整回答
 ↓
Browser
```

Streaming：

```text
User
 ↓
FastAPI
 ↓
LLM
 ↓
token
token
token
token
 ↓
SSE
 ↓
Browser
```

效果：

```text
用户：
什么是 RAG？

页面：
R
RA
RAG
RAG 是
RAG 是一种
RAG 是一种...
```

关键链路：

```text
LLM Streaming
      ↓
Async Generator
      ↓
SSE
      ↓
Browser
```

---

# 19. Agent Event

进入 Agent 后，不应该只传 token。

应该设计统一事件，例如：

```json
{
  "type": "tool_call",
  "task_id": "123",
  "timestamp": "2026-09-26T12:00:00Z",
  "data": {
    "tool": "search",
    "arguments": {
      "query": "FastAPI SSE"
    }
  }
}
```

事件类型可以设计为：

```text
agent_start
agent_end

thinking
token

tool_call
tool_result

rag_search
rag_result

task_start
task_progress
task_end

error
```

统一事件流：

```text
Agent
 ↓
Event Bus
 ↓
SSE / WebSocket
 ↓
Frontend
```

---

# 20. Agent + SSE

SSE 特别适合作为 Agent → UI 的事件输出通道。

```text
                 Agent
                   │
                   ↓
              Event Bus
                   │
                   ↓
                 SSE
                   │
                   ↓
               Browser
```

事件流：

```text
event: agent_start

event: thinking

event: rag_search

event: rag_result

event: tool_call

event: tool_result

event: token
data: 根据

event: token
data: 搜索结果

event: done
```

---

# 21. Agent + WebSocket

WebSocket 更适合 UI → Agent 的实时控制。

```text
Browser
   │
   ├── pause
   ├── resume
   ├── cancel
   ├── approve_tool
   ├── reject_tool
   └── user_input
        │
        ↓
   WebSocket
        │
        ↓
      Agent
```

因此可以建立实用分工：

```text
SSE
    Agent → UI
    主要负责实时事件输出

WebSocket
    UI ↔ Agent
    主要负责实时控制和双向交互
```

这不是绝对规则，实际项目应根据需求选择。

---

# 22. 最终项目：Mini Agent Platform

建议最终做一个：

> **Mini Agent Platform**

整体结构：

```text
                         Browser
                            │
                ┌───────────┴───────────┐
                │                       │
               SSE                 WebSocket
                │                       │
         Agent Event Output       Agent Control
                │                       │
                └───────────┬───────────┘
                            │
                         FastAPI
                            │
                ┌───────────┼───────────┐
                │           │           │
              Agent        RAG        Database
                │
        ┌───────┼────────┐
        │       │        │
       LLM     Tools    Memory
```

---

# 23. 项目目录

```text
agent-platform/
│
├── backend/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── chat.py
│   │   ├── agent.py
│   │   └── websocket.py
│   │
│   ├── services/
│   │   ├── agent_service.py
│   │   ├── rag_service.py
│   │   └── llm_service.py
│   │
│   ├── streaming/
│   │   ├── sse.py
│   │   └── events.py
│   │
│   ├── models/
│   │
│   └── core/
│
├── frontend/
│
└── tests/
```

---

# 24. 通过 8 个版本逐步实现

## v0：Hello API

实现：

```text
GET /hello
POST /chat
```

目标：

```text
HTTP
FastAPI
Pydantic
```

## v1：CRUD API

实现：

```text
/tasks

GET
POST
PUT
DELETE
```

目标：

```text
REST API
Path
Query
Body
Response
Validation
```

## v2：HTTP Streaming

实现：

```text
GET /stream
```

服务器：

```text
1
2
3
4
5
...
```

目标：

```text
async generator
yield
StreamingResponse
```

## v3：SSE

实现：

```text
GET /events
```

事件：

```text
status
progress
message
done
```

目标：

```text
SSE
EventSource
事件格式
断线重连
```

## v4：WebSocket Chat

实现：

```text
/ws
```

支持：

```text
Client → Server
Server → Client
Broadcast
```

目标：

```text
WebSocket
Connection
Connection Manager
```

## v5：LLM Agent

加入：

```text
LLM
Tool
Memory
RAG
```

整体：

```text
User
 ↓
FastAPI
 ↓
Agent
 ↓
LLM
 ↓
Tool
 ↓
RAG
```

## v6：统一 Agent Event

建立：

```python
{
    "type": "...",
    "task_id": "...",
    "timestamp": "...",
    "data": {}
}
```

例如：

```text
agent_start
tool_call
tool_result
rag_search
rag_result
token
error
done
```

然后：

```text
Agent
 ↓
Event Bus
 ↓
SSE / WebSocket
 ↓
Frontend
```

这是最值得深入的一步。

## v7：Agent Control

WebSocket 增加：

```text
pause
resume
cancel
approve
reject
send_message
```

形成：

```text
Agent Output
       ↓
      SSE

Agent Control
       ↓
   WebSocket
```

## v8：生产化

加入：

```text
Redis
PostgreSQL
Nginx
Docker
Authentication
Multiple Workers
Logging
Metrics
Retry
Reconnect
Heartbeat
```

最终：

```text
                    Browser
                       │
              ┌────────┴────────┐
              │                 │
             SSE           WebSocket
              │                 │
              └────────┬────────┘
                       │
                     Nginx
                       │
                    FastAPI
                       │
             ┌─────────┼─────────┐
             │         │         │
           Agent      Redis    PostgreSQL
             │
       ┌─────┼─────┐
       │     │     │
      LLM   RAG   Tools
```

---

# 25. 完整学习顺序

```text
01. Python async/await
        ↓
02. HTTP
        ↓
03. REST API
        ↓
04. FastAPI
        ↓
05. Pydantic
        ↓
06. ASGI / Starlette / Uvicorn
        ↓
07. StreamingResponse
        ↓
08. SSE
        ↓
09. WebSocket
        ↓
10. Connection Manager
        ↓
11. Redis / PubSub
        ↓
12. LLM Streaming
        ↓
13. Agent Event System
        ↓
14. Agent + SSE
        ↓
15. Agent + WebSocket
        ↓
16. 完整 Agent Server
        ↓
17. Nginx / Docker / 多 Worker / 生产化
```

---

# 26. 每个阶段的核心问题

## Async

```text
为什么要 async？
await 到底发生了什么？
Task 是什么？
Event Loop 在干什么？
```

## HTTP

```text
Request 和 Response 怎么组成？
HTTP 是不是一定一次请求一次响应？
长连接是什么？
```

## FastAPI

```text
FastAPI 和 Uvicorn 什么关系？
FastAPI 和 Starlette 什么关系？
请求怎么进入 Python 函数？
```

## Streaming

```text
为什么可以边生成边返回？
yield 在这里起什么作用？
```

## SSE

```text
SSE 和普通 Streaming 有什么区别？
为什么 SSE 可以自动重连？
为什么 SSE 适合 LLM？
```

## WebSocket

```text
为什么需要 WebSocket？
为什么它能双向通信？
连接如何管理？
多 Worker 怎么办？
```

## Agent

```text
Agent 内部事件怎么表示？
Tool Call 怎么传给前端？
Task 状态放在哪里？
断线以后怎么恢复？
SSE 与 WebSocket 怎么协同？
```

---

# 27. 最终认知框架

```text
┌──────────────────────────────┐
│          Agent Layer         │
│                              │
│ Agent / RAG / Tool / Memory  │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│       Application Layer      │
│                              │
│           FastAPI            │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│       Communication Layer    │
│                              │
│ HTTP / SSE / WebSocket       │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│       Runtime Layer          │
│                              │
│ AsyncIO / ASGI / Uvicorn     │
└──────────────────────────────┘
```

---

# 28. 与 Agent Harness 的联系

你之前学习的：

```text
Agent Loop
Tool Calling
RAG
Memory
Task State
Blackboard
Hooks
Subagent
```

属于 **Agent 内部运行机制**。

而：

```text
HTTP
SSE
WebSocket
FastAPI
```

属于 **Agent 对外服务和通信层**。

两者组合起来：

```text
                   Agent Server
                        │
        ┌───────────────┴────────────────┐
        │                                │
   Communication                    Agent Runtime
        │                                │
 ┌──────┼──────┐                 ┌───────┼───────┐
 │      │      │                 │       │       │
HTTP   SSE   WebSocket          Loop    Tool    RAG
                                      │
                                    Memory
```

> **SSE / WebSocket 不属于 Agent 本身，但它们是 Agent 产品化时非常重要的通信基础设施。**

---

# 29. 最终目标

学完以后，你应该能够独立解释并实现：

```text
浏览器
   │
   │ HTTP
   ▼
FastAPI
   │
   ├── REST API
   │
   ├── SSE
   │     └── LLM / Agent Streaming
   │
   └── WebSocket
         └── Agent Control
                │
                ▼
              Agent
                │
        ┌───────┼───────┐
        │       │       │
       LLM     RAG     Tool
```

最终能够回答：

```text
为什么 LLM Streaming 常用 SSE？
什么时候应该用 WebSocket？
FastAPI 和 Uvicorn 什么关系？
ASGI 解决了什么问题？
StreamingResponse 和 SSE 什么关系？
WebSocket 多连接怎么管理？
多 Worker 为什么需要 Redis？
Agent 的事件应该怎么设计？
Agent UI 和 Agent Runtime 如何解耦？
```

---

# 30. 推荐学习方式

不要采用“看完教程再写项目”的方式，而是每学一个层次就做一个最小实验：

```text
asyncio
  ↓
一个并发 Demo

HTTP
  ↓
curl / httpx 请求

FastAPI
  ↓
Hello API

Streaming
  ↓
逐块输出数字

SSE
  ↓
实时事件页面

WebSocket
  ↓
双向聊天

Redis
  ↓
多 Worker 事件同步

LLM
  ↓
Token Streaming

Agent
  ↓
Tool / RAG / Event
```

这样学习的重点不是“记住 FastAPI API”，而是逐层建立：

```text
网络通信
   ↓
异步运行时
   ↓
Web 框架
   ↓
流式传输
   ↓
实时通信
   ↓
AI Streaming
   ↓
Agent Server
```

最终形成完整的后端与 Agent 通信心智模型。
