# 从 HTTP 到实时 Agent Server
### 给已入门 Agent/RAG 的你：网络通信与流式服务课程

> **课程定位**：你已经会写 Agent（loop、tool calling）和 RAG，但这些能力还困在一个 Python 进程里。这门课只教一件事——**把 Agent 接到网络上，变成别人能打开、能看着它思考、能随时打断它的产品**。
>
> 对应的知识底稿：[SSE_WebSocket_FastAPI_完整学习路线.md](SSE_WebSocket_FastAPI_完整学习路线.md)（本课程按其知识链组织，全部落地为可运行实验）
>
> 图表索引（archify 产出，浏览器打开）：[01 全景架构](diagrams/01-agent-server-architecture.html) · [02 SSE 生命周期](diagrams/02-sse-lifecycle.html) · [03 WebSocket 握手](diagrams/03-websocket-handshake.html) · [04 事件管道](diagrams/04-agent-event-pipeline.html) · [05 v7 双通道时序](diagrams/05-agent-server-dual-channel.html) · [06 v8 多 Worker 与 Redis](diagrams/06-multi-worker-redis.html) · [07 Redis 数据面/控制面](diagrams/07-redis-data-plane.html) · [08 流穿 Nginx](diagrams/08-nginx-sse-journey.html) · [09 终极总装](diagrams/09-final-system.html)
>
> 遇到环境报错：先查[排障附录](course/appendix-troubleshooting.md)；改代码/升级依赖后跑 `labs/smoke_test.py` 一键回归。

---

## 1. 学完这门课你能回答什么

```
为什么 LLM Streaming 几乎都用 SSE，而不是轮询或 WebSocket？
StreamingResponse 和 SSE 是什么关系？
FastAPI、Starlette、Uvicorn、ASGI 各自管什么？
浏览器断网 10 秒，Agent 生成到一半，恢复后怎么从断点继续？
Agent 的工具调用怎么实时画到前端？怎么让人类审批一次危险操作？
连接数上千后，进程内存里的连接表和事件缓冲为什么必须搬到 Redis？
```

## 2. 课程结构：8 个模块 / 27 课 / 16 个实验（含 A1 与 v8 配置实验）

教学原则：**每学一层，立刻做一个能跑的最小实验**（不"看完再练"）；每个实验先手动观察（curl/浏览器），再用脚本自动化验证；能复用成熟开源组件就复用，手写只为了看懂协议。

| 模块 | 主题 | 课时 | 实验 | 详细讲义 |
|---|---|---|---|---|
| M0 | 为什么 Agent 开发者需要网络通信 | 2 课 | 观察实验 | [module-0-为什么需要网络通信.md](course/module-0-为什么需要网络通信.md) |
| M1 | 地基：异步与 HTTP | 4 课 | A1, v0 | [module-1-异步与HTTP地基.md](course/module-1-异步与HTTP地基.md) |
| M2 | 流式传输与 SSE | 5 课 | v2, v3a/b/c | [module-2-流式传输与SSE.md](course/module-2-流式传输与SSE.md) |
| M3 | WebSocket 双向通信 | 3 课 | v4 | [module-3-WebSocket双向通信.md](course/module-3-WebSocket双向通信.md) |
| M4 | LLM 流式与 Agent 事件系统 | 4 课 | v5, v6, v7 | [module-4-LLM流式与Agent事件.md](course/module-4-LLM流式与Agent事件.md) |
| M5 | 综合项目与生产化 | 2 课 | v8 | [module-5-综合项目与生产化.md](course/module-5-综合项目与生产化.md) |
| M6 | 生产基础设施 I · Redis 事件总线 | 4 课 | r1/r2/r3 | [module-6-Redis事件总线.md](course/module-6-Redis事件总线.md) |
| M7 | 生产基础设施 II · Nginx 与部署 | 3 课 | n1/n2 | [module-7-Nginx与部署.md](course/module-7-Nginx与部署.md) |

### 课时明细

**M0 为什么需要网络通信**
- L0.1 三种通信模型：一问一答 / 单向直播 / 双向对话（生活比喻 + `curl` 观察）
- L0.2 全景地图：你的 Agent 知识在里层，通信层在外层——它们在哪条线上相遇

**M1 异步与 HTTP 地基**
- L1.1 Python 异步：阻塞的代价、事件循环、Task、Queue（实验 A1）
- L1.2 HTTP 报文解剖：请求/响应的结构、方法、状态码、Headers
- L1.3 长连接与 Keep-Alive：为流式铺路
- L1.4 第一个 FastAPI：路由、Pydantic、OpenAPI（实验 v0）

**M2 流式传输与 SSE**
- L2.1 ASGI 分层：请求从浏览器到你的函数经过谁（架构图 01）
- L2.2 StreamingResponse：`yield` 如何变成 HTTP chunk（实验 v2）
- L2.3 SSE 协议格式精讲：手写一遍报文（实验 v3a）
  - 配套互动课：[lessons/0002 SSE 格式实验室](lessons/0002-sse-format-lab.html)（可编辑报文 + 实时解析）
- L2.4 生产级 SSE：fastapi.sse 原生支持、心跳、断线续传（实验 v3b）
- L2.5 sse-starlette 与生态对照：存量项目怎么写、MCP Streamable HTTP（实验 v3c）

**M3 WebSocket 双向通信**
- L3.1 握手与生命周期：HTTP Upgrade、帧、ping/pong、关闭码（架构图 03）
- L3.2 FastAPI WebSocket 实战：echo → 聊天室（实验 v4）
- L3.3 ConnectionManager 与广播：多连接管理、SSE vs WebSocket 选型

**M4 LLM 流式与 Agent 事件系统**
- L4.1 LLM Token Streaming 全链路：SDK → generator → SSE → 打字机（实验 v5）
- L4.2 统一 Agent 事件协议：对齐 AG-UI / Dify 的事件设计（实验 v6 events.py）
- L4.3 事件流架构：Agent Runtime 与通信层解耦（实验 v6）
- L4.4 双通道 Agent Server：SSE 直播 + WebSocket 遥控 + 人工审批（实验 v7，毕业实验）
  - 配套互动课：[lessons/0003 Agent 事件时间线浏览器](lessons/0003-agent-event-explorer.html)（单步回放一次真实任务的事件流）· 配图 05

**M5 综合项目与生产化**
- L5.1 Mini Agent Platform 复盘与扩展练习
- L5.2 生产化：Nginx、多 Worker、Redis Pub/Sub、Docker（实验 v8）
  - 配图 06：为什么进程内存必须外移到 Redis

**M6 生产基础设施 I · Redis 事件总线**
- L6.1 为什么是 Redis：三个进程内存结构的宿命（Hash/Stream/Pub/Sub 对号入座）
- L6.2 r1：任务表 → Hash（适配层设计 + 跨连接验证）
- L6.3 r2：事件日志 → Stream（XADD/XRANGE + 跨进程 Last-Event-ID 续传）
- L6.4 r3：Pub/Sub 跨 Worker 广播 + 控制平面路由（双进程端到端验证）

**M7 生产基础设施 II · Nginx 与部署**
- L7.1 反向代理：流式服务的三组生死配置（buffering / read_timeout / Upgrade）
- L7.2 n1：事故解剖——read_timeout 掐流复现与心跳救命
- L7.3 n2：完整体系总装（Nginx → Worker×2 → Redis 全链路验证）

## 3. 实验索引（labs/，全部实测可运行）

| 实验 | 一句话目标 | 启动命令（labs/ 下） |
|---|---|---|
| [A1](labs/a1_async/asyncio_basics.py) | 亲眼看见"并发"发生 | `python a1_async/asyncio_basics.py` |
| [v0](labs/v0_hello_api/) | 第一个 FastAPI 服务 | `python -m uvicorn v0_hello_api.app:app --port 8801 --reload` |
| [v2](labs/v2_streaming/) | 分块响应 vs 整块响应 | `python -m uvicorn v2_streaming.app:app --port 8802 --reload` |
| [v3a](labs/v3_sse/) | 手写 SSE 裸格式 | `python -m uvicorn v3_sse.v3a_raw_sse:app --port 8803 --reload` |
| [v3b](labs/v3_sse/) | 原生 SSE + 断线续传 + POST/SSE | `python -m uvicorn v3_sse.v3b_fastapi_sse:app --port 8803 --reload` |
| [v3c](labs/v3_sse/) | sse-starlette（存量项目标准） | `python -m uvicorn v3_sse.v3c_sse_starlette:app --port 8803 --reload` |
| [v4](labs/v4_websocket/) | echo → 聊天室 → 连接管理 | `python -m uvicorn v4_websocket.app:app --port 8804 --reload` |
| [v5](labs/v5_llm_stream/) | LLM token 流全链路 | `python -m uvicorn v5_llm_stream.app:app --port 8805 --reload` |
| [v6](labs/v6_agent_events/) | 统一 Agent 事件流 | `python -m uvicorn v6_agent_events.app:app --port 8806 --reload` |
| [v7](labs/v7_agent_server/) | **毕业：SSE 直播 + WS 遥控** | `python -m uvicorn v7_agent_server.app:app --port 8807 --reload` |
| [r1](labs/r1_redis_tasks/) | 任务表 → Redis Hash | `python -m uvicorn r1_redis_tasks.app:app --port 18901` |
| [r2](labs/r2_redis_stream/) | 事件日志 → Redis Stream | `python r2_redis_stream/verify_replay.py` |
| [r3](labs/r3_redis_fanout/) | 多进程 Agent Server（v7 完全体） | `python r3_redis_fanout/verify_multiworker.py` |
| [n1](labs/n1_nginx_proxy/) | Nginx 缓冲/超时事故对照 | `python n1_nginx_proxy/verify_through_nginx.py` |
| [n2](labs/n2_full_stack/) | 终极拓扑全链路验证 | `python n2_full_stack/verify_topology.py` |
| [v8](labs/v8_production/) | 生产化：Nginx/Docker/多 Worker 设计（文档+配置） | - |
| [smoke_test.py](labs/smoke_test.py) | 一键回归全部实验（改代码/升级依赖后必跑） | `python smoke_test.py` |

环境准备：`cd labs && python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements.txt`
报错先查[排障附录](course/appendix-troubleshooting.md)。

## 4. 建议节奏（6 周，每天 40–60 分钟）

| 周 | 内容 | 通关标准 |
|---|---|---|
| 1 | M0 + M1 | 不看资料说出 HTTP 响应三段结构；向别人解释 `await` 时发生了什么 |
| 2 | M2 L2.1–L2.3 | 能在纸上写出一条合法 SSE 报文；解释 chunked 与 SSE 的关系 |
| 3 | M2 L2.4–L2.5 | 断网重连实验成功（Last-Event-ID 续传）；说出心跳的两个作用 |
| 4 | M3 | 两个标签页聊天室互发；说出"什么场景必须 WS"的两个例子 |
| 5 | M4 L4.1–L4.3 | 打字机效果跑通；把 v6 事件表与 AG-UI/Dify 对照讲解 |
| 6 | M4 L4.4 + M5 | **毕业实验 v7 全流程**（暂停/恢复/取消/审批全部操作成功）+ 读一份真实项目的 SSE 代码 |
| 7 | M6 | verify_multiworker.py 全绿（双进程暂停/审批/续传） |
| 8 | M7 | verify_topology.py 全绿（经 Nginx 的全链路）+ 生产检查清单过一遍 |

## 5. 参考的成熟开源项目（学"别人的轮子"在哪）

| 阶段 | 项目 | 学什么 | 课程落点 |
|---|---|---|---|
| SSE 服务端 | [fastapi/sse 教程](https://fastapi.tiangolo.com/tutorial/server-sent-events/) · [sse-starlette](https://github.com/sysid/sse-starlette) | 生产 SSE 的心跳/续传/超时 | v3b/v3c 直接使用，不重复造轮子 |
| WebSocket 模式 | [FastAPI 官方 WebSockets 示例](https://fastapi.tiangolo.com/advanced/websockets/) | ConnectionManager 范式 | v4 沿用其结构 |
| LLM 流式 | [openai-python streaming](https://github.com/openai/openai-python/blob/main/api.md#streaming-responses) | SDK 流式接口形态、`[DONE]` 哨兵 | v5 对齐其约定 |
| Agent 事件协议 | [AG-UI](https://docs.ag-ui.com/concepts/events) · [Dify](https://github.com/langgenius/dify) | 三段式事件、生命周期、审批中断 | v6/v7 事件命名对齐 |
| Agent 生态传输 | [MCP Transports](https://modelcontextprotocol.io/docs/concepts/transports) | Streamable HTTP = POST + SSE | v3b 的 POST/SSE 就是它的雏形 |
| 生产级全貌 | [Dify](https://github.com/langgenius/dify) · [LibreChat](https://github.com/danny-avila/LibreChat) · [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) | 真实项目怎么组织通信层 | M5 阅读作业 |

## 6. 学习方法约定

1. **读 → 跑 → 改 → 讲**：先跑通实验（跑），改一个参数看现象（改），最后向别人（或向 AI）复述流程（讲）。
2. **检索练习**：每个实验 README 末尾有自测问题，先回忆再翻答案级文档。
3. **穿插**：M2 之后回到 M1 的 A1 脚本，用 SSE 视角重新解释 Queue 演示。
4. 遇到卡点：直接在对话里问（`/teach` 会话中），讲师会基于你的学习记录调整下一课。
5. 课程文档是主教材；`lessons/` 下的 HTML 课是复习卡；`reference/` 下的速查表供写代码时对照；术语见 [GLOSSARY.md](GLOSSARY.md)。

## 7. 毕业标准

- [ ] 能白板画出 Mini Agent Platform 全景架构（对照架构图 01，不看原图）
- [ ] v7 毕业实验五项操作全通：启动、暂停/恢复、取消、审批/拒绝、断线重连续传
- [ ] 用自己的话写出 9 个核心问题的答案（见顶部"学完你能回答什么"）
- [ ] 挑一个真实开源项目（Dify/LibreChat 任一），读懂它的 SSE 端点并在 issue/笔记里画出它的事件类型表
