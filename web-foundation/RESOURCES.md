# Resources: 网络通信 × Agent Server

## Knowledge

### 协议与标准（一手来源）

- [MDN: HTTP 概述](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Overview) — HTTP 报文、方法、状态码的权威入门。用于：模块 1 的 HTTP 课。
- [MDN: Server-sent events](https://developer.mozilla.org/zh-CN/docs/Web/API/Server-sent_events) — SSE 浏览器端 API（EventSource）与事件流格式的标准文档。用于：模块 2。
- [WHATWG HTML 规范：server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html#server-sent-events) — SSE 的最终规范（事件流格式、重连规则、Last-Event-ID）。用于：需要裁定"为什么"时。
- [MDN: WebSocket API](https://developer.mozilla.org/zh-CN/docs/Web/API/WebSockets_API) — 浏览器 WebSocket API、握手、帧、关闭码。用于：模块 3。
- [RFC 9110（HTTP 语义）](https://httpwg.org/specs/rfc9110.html) — 状态码与方法语义的权威定义。用于：查阅，不通读。
- [ASGI 规范](https://asgi.readthedocs.io/en/latest/) — Uvicorn ↔ Starlette/FastAPI 之间的接口标准。用于：模块 2 理解分层。

### 框架与库（本项目直接使用）

- [FastAPI 官方文档](https://fastapi.tiangolo.com/zh/) — 主教材。重点：Tutorial 全部、[SSE 教程](https://fastapi.tiangolo.com/tutorial/server-sent-events/)、[WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)、[StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)。
- [sse-starlette (GitHub)](https://github.com/sysid/sse-starlette) — FastAPI 原生 SSE 出现之前的事实标准库：心跳 ping、send_timeout、Last-Event-ID 处理。用于：v3c 实验与生产方案对比。
- [Uvicorn 部署文档](https://www.uvicorn.org/deployment/) — workers、进程模型、Nginx 反代。用于：模块 5 生产化。
- [Redis Pub/Sub 文档](https://redis.io/docs/latest/develop/use/pubsub/) — 多 Worker 广播的标准答案。用于：M6。
- [Redis Streams 教程](https://redis.io/docs/latest/develop/data-types/streams-tutorial/) — XADD/XRANGE/消费者组的一手资料。用于：M6 r2/r3。
- [fakeredis](https://fakeredis.readthedocs.io/) — 纯 Python Redis 仿真，实验降级方案。用于：labs 适配层。
- [Nginx beginner's guide](https://nginx.org/en/docs/beginners_guide.html) — 配置结构（http/server/location）官方入门。用于：M7。
- [Nginx 反代文档](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) — proxy_buffering/read_timeout 等指令的权威定义。用于：M7 n1。
- [httpx 文档](https://www.python-httpx.org/) — Python 客户端，实验中用于测试 API 和消费流。

### LLM / Agent 流式协议（设计参考）

- [OpenAI Python SDK: streaming](https://github.com/openai/openai-python/blob/main/api.md#streaming-responses) — `stream=True` 的官方用法；LLM token 流的源头。用于：v5。
- [AG-UI 协议：事件模型](https://docs.ag-ui.com/concepts/events) — CopilotKit 主导的 Agent↔前端事件协议：RUN_STARTED/TEXT_MESSAGE_*/TOOL_CALL_* 三段式、快照+增量。**本课程 Agent 事件设计的首要对齐对象**。用于：模块 4。
- [MCP 规范：Transports](https://modelcontextprotocol.io/docs/concepts/transports) — Agent 生态的协议层：stdio 与 Streamable HTTP（服务端用 SSE 回流）。用于：模块 2/4 的延伸阅读，理解"SSE 不只是课程知识，是 Agent 生态的底层协议"。
- [Dify API 文档](https://docs.dify.ai/) — 生产级 Agent 平台：streaming 模式下 workflow_started / node_started / node_finished / message / message_end / ping 事件流。用于：模块 4 事件设计的真实世界印证。

### 成熟开源项目（读源码阶段）

- [langgenius/dify](https://github.com/langgenius/dify) — 生产级 Agent/Workflow 平台，SSE 事件流设计可直接借鉴。
- [danny-avila/LibreChat](https://github.com/danny-avila/LibreChat) — 多模型聊天服务，SSE streaming 实现清晰。
- [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) — FastAPI 官方全栈模板：项目结构、认证、部署的参考答案。

## Wisdom (Communities)

- [FastAPI GitHub Discussions](https://github.com/fastapi/fastapi/discussions) — 框架作者与核心贡献者出没；SSE/WebSocket 相关问题先搜这里。
- [MCP GitHub Discussions](https://github.com/modelcontextprotocol/servers/discussions) — MCP 传输层与 Agent 服务化的活跃社区。
- [Python Discord #async-dev](https://discord.com/invite/python) — asyncio 具体问题的快速反馈。
- [r/FastAPI](https://www.reddit.com/r/FastAPI/) — 中等信噪比，适合看别人踩坑。

## Gaps

- 暂缺：系统性的"Agent Server 架构"中文一手资料——目前以 AG-UI 规范 + Dify 源码替代。
- 暂缺：本机 Docker 环境是否可用的确认；v8 生产化实验先以文档 + 配置文件形式交付。
