# labs：渐进式实验区

每个实验只教一件事，都能独立运行。课程文档（`../course/`）会逐段讲解这些代码。

## 准备环境（一次性）

```bash
cd labs
python -m venv .venv
# Windows Git Bash:
source .venv/Scripts/activate
# 或 Windows CMD: .venv\Scripts\activate.bat
pip install -r requirements.txt
```

## 实验索引

| 实验 | 主题 | 端口 | 对应模块 |
|---|---|---|---|
| `a1_async/` | asyncio：协程、Task、Queue（不开服务） | - | 模块 1 |
| `v0_hello_api/` | 第一个 FastAPI：路由、Pydantic、/docs | 8801 | 模块 1 |
| `v2_streaming/` | StreamingResponse：分块响应 | 8802 | 模块 2 |
| `v3_sse/v3a` | 手写 SSE 裸格式（理解协议） | 8803 | 模块 2 |
| `v3_sse/v3b` | FastAPI 原生 SSE + 断线续传 + POST/SSE | 8803 | 模块 2 |
| `v3_sse/v3c` | sse-starlette 生产级方案（心跳） | 8803 | 模块 2 |
| `v4_websocket/` | WebSocket：echo → 聊天室 → ConnectionManager | 8804 | 模块 3 |
| `v5_llm_stream/` | LLM Token Streaming 全链路（mock/真 API） | 8805 | 模块 4 |
| `v6_agent_events/` | 统一 Agent 事件协议 + SSE 事件流 | 8806 | 模块 4 |
| `v7_agent_server/` | **毕业实验**：SSE 输出 + WebSocket 控制 | 8807 | 模块 4/5 |
| `r1_redis_tasks/` | 任务表外移 → Redis Hash | 18901 | 模块 6 |
| `r2_redis_stream/` | 事件日志 → Redis Stream（跨进程续传） | 18902 | 模块 6 |
| `r3_redis_fanout/` | Pub/Sub 跨 Worker 广播（多进程全验证） | 18901/2 | 模块 6 |
| `n1_nginx_proxy/` | Nginx 反代：超时掐流事故对照 | 8080→8807 | 模块 7 |
| `n2_full_stack/` | 终极拓扑：Nginx → Worker×2 → Redis | 8080 | 模块 7 |
| `v8_production/` | 生产化：Nginx/Docker/多 Worker 设计（文档+配置） | - | 模块 5 |

> r 系/n 系依赖基础设施：Redis 用官方镜像
> `docker run -d --name course-redis -p 6399:6379 redis:7-alpine`；
> Nginx 用 `nginx:1.28-alpine` 容器（实验脚本自动起停）。

## 通用习惯

- 服务端启动统一是：`python -m uvicorn <模块>:app --port <端口> --reload`
- 客户端观察统一用三种工具：`curl -N`（看原始字节）、浏览器（看真实行为）、`httpx`/`websockets` 脚本（做自动化验证）
- 每个 lab 的 README 末尾有「自测问题」，答不上来说明还没学透，回课程文档对应小节
- **改完代码或升级依赖后，跑 `python smoke_test.py` 一键回归全部实验**（也可以 `python smoke_test.py v3b v7` 只跑指定项）
