# Mission: 给 Agent 开发者的网络通信课（HTTP → Streaming → SSE → WebSocket → Agent Server）

## Why

用户已经掌握了 Agent 基础（agent loop、tool calling）与 RAG 基础，但这些能力目前只存在于"进程内部"。要让 Agent 变成别人真正能用、能看、能控制的产品，必须掌握它对外的通信层：HTTP、流式传输、SSE、WebSocket，以及承载它们的 FastAPI/ASGI。本课程的目标是补齐这最后一层，让"会做 Agent"升级为"会做 Agent Server"。

## Success looks like

- 能向别人讲清楚：为什么 LLM Streaming 几乎都用 SSE，什么时候必须换 WebSocket
- 能从零实现并调试一条完整链路：LLM token 流 → async generator → SSE → 浏览器打字机效果
- 能实现 WebSocket 控制通道：对运行中的 Agent 发出 pause / resume / cancel / approve_tool
- 能设计一套统一的 Agent 事件协议（对齐 AG-UI / Dify 的事件模型，而不是自己发明）
- 读懂 Dify、LibreChat、sse-starlette 等开源项目的通信层代码不再吃力
- 毕业项目：一个可运行的 Mini Agent Platform（SSE 输出 + WebSocket 控制 + 简易 UI）

## Constraints

- 初学者视角：网络与后端基础薄弱，需要从 HTTP 报文级别讲起，不假设懂 TCP/前端框架
- 中文教学；每学一层就做一个能跑起来的最小实验，不搞"看完再练"
- 优先复用成熟开源组件（如 fastapi.sse / sse-starlette），只在理解目的时手写一遍
- 参考 `SSE_WebSocket_FastAPI_完整学习路线.md` 的知识链条组织内容

## Out of scope

- 前端框架工程化（React/Vue/构建工具），只用原生 HTML/JS 做演示页面
- TCP/IP 协议栈底层实现、网络抓包分析工具链
- Kubernetes、服务网格等大规模运维话题
- Agent 内部机制（loop / RAG / memory）的重新学习——只负责把它们"接出来"
