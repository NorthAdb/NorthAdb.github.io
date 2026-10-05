# 模块 5：综合项目与生产化

> 2 课 · 实验 v8（文档+配置）· 目标：把毕业实验"搬进"真实部署环境，理解每一层为什么存在

---

> 配图：多 Worker 与 Redis [diagrams/06-multi-worker-redis.html](../diagrams/06-multi-worker-redis.html)——先看这张图再读下文，"三处碎裂"一目了然。

## L5.1 Mini Agent Platform 复盘与扩展练习

### 目标
白板复述全景架构；明确 v7 → "可上线的 Agent 平台"之间还差什么。

### 复盘（对照三张图）

- 全景架构 [diagrams/01-agent-server-architecture.html](../diagrams/01-agent-server-architecture.html)：从 Browser 到 LLM 的每条线，说出协议与方向。
- SSE 生命周期 [diagrams/02-sse-lifecycle.html](../diagrams/02-sse-lifecycle.html)：断线重连的每个参与者动作。
- 事件管道 [diagrams/04-agent-event-pipeline.html](../diagrams/04-agent-event-pipeline.html)：Agent → Event Bus → SSE/WS → UI 的数据流。

### 扩展练习（按兴趣选做）

1. **接真模型**：把 v5 的 openai_stream 接进 v7 的 agent 步骤 3（生成阶段）。
2. **接真 RAG**：步骤 1 的 mock 检索换成你已掌握的 RAG 管线；rag_search/rag_result 事件照发。
3. **任务持久化**：TASKS 字典换 SQLite（SQLModel），重启服务后历史任务可回放。
4. **事件持久化**：buffer 落库，replay 端点改为查库。

---

## L5.2 生产化：Nginx、多 Worker、Redis Pub/Sub、Docker

### 目标
说出单进程方案在三个场景下的碎裂方式，以及对应的生产解法；读懂 v8 的 Nginx 配置。

### 1) Nginx：流式的头号杀手是缓冲

v8 的 nginx.conf 关键三处：
- `proxy_buffering off`（或依赖 FastAPI 自动带的 `X-Accel-Buffering: no`）——否则 SSE token 被 Nginx 攒着，用户看到"卡一下全出来"（L2.2 curl 缓冲对照实验的翻版）；
- `proxy_read_timeout 3600s`——默认 60s 读超时会掐断长连接；**心跳的第二个价值**：15s 一次的 `: ping` 让 read timer 永远不会被触发；
- WS 的 `Upgrade`/`Connection` 头透传（`map $http_upgrade` 块）。

### 2) 多 Worker：进程内状态的三处碎裂

`uvicorn --workers 4` 时，v7 的 `TASKS`、`buffer`、`hub.clients` 都在各自进程内存里：
- 创建任务打到 worker1，SSE 订阅打到 worker2 → **404**；
- WS 控制指令打到 worker3 → **操作不了 worker1 的任务**；
- ControlHub 只能广播给连在本进程的 WS 客户端。

**标准解法：Redis**
| v7 进程内结构 | Redis 原语 | 用法 |
|---|---|---|
| TASKS 任务表 | Hash | `HSET agent:tasks {id} {meta}` |
| buffer 事件日志 | Stream | `XADD agent:{id}:events * ...`；`XRANGE` 按 id 续传（天然支持 Last-Event-ID 语义） |
| ControlHub 广播 | Pub/Sub | worker 收到任务事件后 `PUBLISH`；每个 worker 订阅并把消息转发给本地连接 |

改造点只有两处（v8 README 有详细步骤）：`emit()` 加一行 publish；每个 worker 启动一个后台协程 subscribe → 投递本地队列。**事件的生产/消费代码不变**——这是 L4.3 解耦设计的直接回报。

### 3) Docker：一条命令拉起拓扑

```
Browser → Nginx(80) → uvicorn×N(8807) → Redis / PostgreSQL
```
`docker compose up --build`（labs/v8_production/docker-compose.yml）。检查清单见 v8 README（认证、超时、指标、优雅停机……）。

### 安全与可观测（清单里最容易被初学者跳过、上线后最先爆的两项）

- WS/SSE 端点认证：连接时校验 token；SSE 校验任务归属（别人的任务 ID 不能白嫖事件）。
- 指标：连接数、事件吞吐、token 首字延迟（TTFT）、P95——流式系统的体验问题都藏在 P95 里。

### 自测（labs/v8_production/README.md 3 题）
1. 心跳为什么能同时解决"读超时"和"中间设备空闲断连"？
2. Last-Event-ID 续传在多 Worker 下还成立吗？事件日志必须存在哪里？
3. v7 哪三个数据结构要搬 Redis？各用什么原语？

---

## 课程终点检查（对照 COURSE.md 第 7 节）

- [ ] 白板画出全景架构
- [ ] v7 五项操作全通
- [ ] 9 个核心问题用自己的话写出答案
- [ ] 读一份真实项目的 SSE 代码（Dify `api/core/workflow/` 或 LibreChat `api/server/routes/`），画出它的事件类型表

完成后：你在 Agent 领域的下一步是 **MCP 服务端开发**（你会发现它的 Streamable HTTP 传输层就是这门课的 POST+SSE）和 **AG-UI 协议接入**（把你 v7 的事件协议升级为标准协议）。
