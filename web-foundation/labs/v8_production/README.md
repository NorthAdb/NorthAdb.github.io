# v8 生产化：多 Worker、反向代理与部署配置（文档 + 配置，动手前先读懂 v7）

实验 v7 的 Mini Agent Server 是**单进程**的。要变成"生产可用"，要解决三件事：
反向代理不吞流、多 Worker 共享连接与事件、容器化交付。本目录给出配置与设计说明。

## 1. Nginx 反向代理：SSE/WebSocket 的头号杀手是缓冲

`nginx.conf` 的关键三处：

- `proxy_buffering off;`（或让 FastAPI 的 `X-Accel-Buffering: no` 响应头生效——fastapi.sse 已自动带）
  否则 SSE token 会被 Nginx 攒在缓冲区里，用户看到的是"卡一下全出来"。
- `proxy_read_timeout 3600s;` SSE 是长连接，默认 60s 读超时会掐断你的流（心跳的价值就在这里：15s 一次的 `: ping` 让 read timer 不断重置）。
- WebSocket 的 `Upgrade`/`Connection` 头透传（http 块的 `map $http_upgrade` 部分）。

## 2. 多 Worker：为什么单进程方案会碎掉

```
uvicorn --workers 4  （或 gunicorn -k uvicorn.workers.UvicornWorker -w 4）
   worker1: TASKS = {...}   ← 任务 A 在这里
   worker2: TASKS = {...}   ← SSE 订阅者可能连到这里
   worker3: TASKS = {...}
   worker4: TASKS = {...}
```

v7 的 `TASKS`、`buffer`、`hub.clients` 全在进程内存里：
- 创建任务的 POST 打到 worker1，SSE 订阅打到 worker2 → **404**；
- WebSocket 控制指令发到 worker3 → **操作不了 worker1 里的任务**；
- ControlHub 只能广播给连在本进程上的 WS 客户端。

**标准解法（Redis Pub/Sub）**：进程内事件照常产生，同时 publish 到 Redis 频道
（如 `agent:{task_id}:events`）；每个 worker subscribe 自己关心的频道，收到后转发给
本地连接。这样"事件日志"从进程内存挪到了 Redis（可再持久化到 PostgreSQL）。

练习（有 Docker 时）：`docker compose up` 启动本目录的 docker-compose.yml，
然后把 v7 改造成 Redis 版——改动点只有两处：
1. `AgentTask.emit()` 里加 `redis.publish(channel, ev.model_dump_json())`；
2. 每个 worker 启动一个后台协程 subscribe 频道，把消息 `put_nowait` 进本地订阅者队列。
buffer（重放依据）改存 `Redis Stream`（`XADD/XRANGE` 天然支持按 id 续传）。

## 3. 部署拓扑与检查清单

```
Browser ──HTTP/SSE/WS──▶ Nginx(80) ──▶ uvicorn ×N(8807)
                                          ├─ Redis      （事件总线/会话）
                                          └─ PostgreSQL （任务/事件持久化）
```

上线前逐项检查：

- [ ] SSE 响应无缓冲（`X-Accel-Buffering: no` 或 Nginx `proxy_buffering off`）
- [ ] 心跳已启用（fastapi.sse 内置 15s；sse-starlette 设 `ping=`）
- [ ] 客户端断线重连 + `Last-Event-ID` 续传已测试（v7 已实现）
- [ ] 多 Worker 下事件经由 Redis 广播，任务状态存 Redis/DB
- [ ] WS 有认证（连接时校验 token），SSE 端点校验任务归属
- [ ] 超时与重试：LLM 调用设置合理 timeout，事件消费有 backpressure 策略
- [ ] 日志与指标：连接数、事件吞吐、token 延迟（P50/P95）
- [ ] 优雅停机：`SIGTERM` 后先完成/取消运行中任务，再退出

## 自测问题

1. 为什么"心跳"能同时解决 Nginx 读超时和中间设备空闲断连两个问题？
2. `Last-Event-ID` 续传在多 Worker 下还成立吗？事件日志必须存在哪里？
3. v7 里哪三个数据结构必须搬到 Redis？各对应 Redis 的什么原语？
   （提示：TASKS→Hash、buffer→Stream、hub→Pub/Sub）
