# r3 · 多进程 Agent Server（Redis 数据面 + 控制面）——v7 的完全体

目标：v7 在多 Worker 下必碎的三个场景，在这里全部修复并**用两个真实进程验证**。
这是课程的收官实验：完成后你就拥有了一整套可水平扩展的 Agent Server。

## 前置

```bash
docker run -d --name course-redis -p 6399:6379 redis:7-alpine   # 真 Redis（本实验必需）
```

## 三个结构的外移（v7 → r3 对照表）

| v7（进程内存） | r3（Redis） | 解决的问题 |
|---|---|---|
| `TASKS` 字典 | Hash `agent:tasks` | 创建与查询落在不同 Worker → 404 |
| `buffer` 列表 | Stream `agent:{id}:events` | 断线重连到别的 Worker 无法补发 |
| `ControlHub` 单进程广播 | Pub/Sub 双频道 | 控制命令无法跨进程送达属主 |

## 启动与观察

```bash
# 一个终端：Worker A
python -m uvicorn r3_redis_fanout.app:app --port 18901
# 另一个终端：Worker B（同一份代码、同一个 Redis）
python -m uvicorn r3_redis_fanout.app:app --port 18902
```

浏览器打开 `http://127.0.0.1:18901/` 启动任务，再开 `http://127.0.0.1:18902/` 的
任务列表——两个"Worker"通过 Redis 看到同一个世界。

自动化验证（**本课程最重要的一条命令**）：
```bash
python r3_redis_fanout/verify_multiworker.py
```
它起两个真实进程：在 A 上创建任务、从 B 消费全部 40+ 条事件、经 B 的 WebSocket
发送暂停/恢复/审批并确认全部生效。

## 代码流程讲解（三个新设计）

1. **seq 由 Redis INCR 保证**（agent.py emit）：`len(buffer)` 只在本进程有意义；
   `INCR agent:{id}:seq` 是跨进程原子操作，seq 的"单调唯一"性质得以保留。
2. **事件双写**：emit() = `XADD`（历史，可回放）+ `PUBLISH`（实时，广播）。
   前者是持久层，后者是通知层——不是二选一，是配合使用。
3. **控制平面路由**（agent.py `control_listener`）：暂停闸门（Event）和审批闸门
   （Future）在属主进程的协程里，别的进程碰不到。任何 Worker 的 WS 命令
   都发布到 `agent:control:{id}` 频道，**属主的 listener** 收到后执行闸门操作。
   执行结果（task_state 事件）走同一条数据面广播，UI 无需专门的状态接口。

## 两个 Pub/Sub 生产陷阱（代码里有对策，必须知道）

1. **Pub/Sub 不留存消息**：发布时属主订阅未就绪 → 消息消失。
   对策：客户端控制带"重发直到看到状态反馈"（verify 脚本 send_until 就是这么写的）。
2. **Pub/Sub 与 Stream 配合**：实时性交给 Pub/Sub（快、可丢），
   可靠性交给 Stream（必达、可回放）——丢了的实时消息总能从 Stream 补回来。

## 自测问题

1. 暂停闸门（asyncio.Event）能不能也搬进 Redis？为什么闸门必须在属主进程？
2. approve 命令发布后 0.5 秒，用户又点了一次"批准"——代码为什么不会重复触发工具？
3. B 的 SSE 为什么能看到 A 的任务事件？画出从 emit 到浏览器的完整路径。
4. 如果 A 进程崩溃，运行中的任务怎么办？状态查询返回什么？（提示：Hash 里还是
   running——生产需要一个"心跳+超时接管"机制，这是留给你的一道扩展题）

## 延伸

- 把事件信封映射到 AG-UI 协议（RUN_STARTED/TEXT_MESSAGE_*），你的 r3 就能接标准前端。
- 事件量大了以后，把 XRANGE 全量+过滤换成"业务 seq 编码进 Stream 条目 ID"的增量读。
