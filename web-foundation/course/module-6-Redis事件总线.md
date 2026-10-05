# 模块 6：生产基础设施 I —— Redis 事件总线

> 4 课 · 实验 r1/r2/r3 · 目标：把 v7 留下的三个"进程内存结构"全部外移，
> 让 Agent Server 从"单进程玩具"变成"可水平扩展的服务"

> 配图：v8 多 Worker 概览 [diagrams/06-multi-worker-redis.html](../diagrams/06-multi-worker-redis.html) · Redis 数据面 [diagrams/07-redis-data-plane.html](../diagrams/07-redis-data-plane.html)

---

## L6.1 为什么是 Redis：三个结构的宿命

### 目标
不看资料说出 v7 的哪三个结构会碎、各自对应 Redis 的哪个原语。

### 概念

v7 毕业实验跑在单进程里，靠三个进程内存结构撑起全部能力。`uvicorn --workers 2` 的瞬间，它们同时碎裂：

| v7 结构 | 职责 | 多进程碎裂方式 | Redis 答案 |
|---|---|---|---|
| `TASKS` 字典 | 任务元数据 | 创建打到 Worker1、查询打到 Worker2 → 404 | **Hash** |
| `buffer` 列表 | 事件历史（续传依据） | SSE 重连到别的 Worker → 补不了事件 | **Stream** |
| `ControlHub` | WS 状态广播/命令 | 广播只达本进程连接 → 遥控失灵 | **Pub/Sub** |

**为什么恰好是这三个原语**：Hash=可按字段读写的字典；Stream=自带单调 ID 的持久日志
（`XADD` 写入、`XRANGE` 按区间读——天然就是"事件日志 + 断点续传"）；Pub/Sub=即发即弃的多进程广播。

### Redis 从哪来（版本说明）

- **课程标准**：Docker 官方镜像 `redis:7-alpine`——
  `docker run -d --name course-redis -p 6399:6379 redis:7-alpine`
- 为什么是 7.x：官方 Redis 不支持 Windows 原生；生产标准是 Linux/Docker 上的 7.x/8.x。
  课程只用 Hash/Stream/Pub/Sub，这些原语从 4.0 起行为一致，任何版本结论相同。
- **代码里的适配层**（labs/redis_client.py）：读 `REDIS_URL` 环境变量连任何实例；
  连不上降级 fakeredis（纯 Python 仿真，单进程内有效）——保证零门槛，也演示"面向接口"设计。
- r1/r2 用同步客户端（命令快、无长等待）；**r3 起必须换 `redis.asyncio`**——
  Pub/Sub 的 `get_message` 会长时间挂起，同步版会卡死整个事件循环（L1.1 教训的翻版）。

### 自测
1. 为什么"任务元数据"对应 Hash 而"事件日志"必须 Stream？（提示：谁需要按序增量读？）
2. fakeredis 降级在哪个实验会失效？为什么？

---

## L6.2 r1：任务表 → Hash

### 目标
实现 TaskStore 适配层；验证"另一个连接"能看到任务。

### 概念
Hash 是"key → field → value"的二级结构：`HSET agent:tasks <task_id> <json>`。
对调用方而言，`STORE.create(...)` 和 v7 的 `TASKS[...] = {...}` **接口一样**——
这就是适配层的意义：换存储，不改业务。

### 实操：实验 r1
```bash
python -m uvicorn r1_redis_tasks.app:app --port 18901
curl -X POST http://127.0.0.1:18901/agent/tasks -H "Content-Type: application/json" -d '{"goal": "r1"}'
docker exec course-redis redis-cli hgetall agent:tasks     # 绕过 HTTP 直查
python r1_redis_tasks/verify_cross_connection.py            # 跨连接验证
```

### 代码流程讲解（r1_redis_tasks/）
1. **store 的四个方法**各对应一条 Redis 命令；`set_state` 在任务生命周期临界点被 agent 调用
   （started→done/cancelled/error），Hash 里的状态始终可信。
2. **`RUNNING` 登记簿留在内存**：它存的是 asyncio.Task 句柄（进程内的执行体）——
   这不是疏忽，是本质：执行体天然属于进程。断线后任务历史靠 Stream（r2），
   控制路由靠 Pub/Sub（r3）。
3. **SSE 端点的 404 语义变了**：任务不在本进程运行时返回 404 并注明"r1 局限"。

### r1 留下的两个局限（写进了 README）
- 事件流仍内存：跨进程回放不行 → r2
- 控制无法跨进程 → r3

---

## L6.3 r2：事件日志 → Stream

### 目标
用 XADD/XRANGE 实现"任何进程都能回放任何任务"；打通跨进程 Last-Event-ID 续传。

### 概念
Stream 的条目自带时间戳形 ID（`ms-us`）和字段集合。我们的设计：
- `XADD agent:{id}:events` 写入字段 `seq / type / ts / data`
- seq 用 **`INCR agent:{id}:seq`** 取——跨进程原子的单调计数器
  （v6/v7 里 `len(buffer)` 只在本进程有意义）
- 回放 = `XRANGE key - +` 全量拉取后按 seq 过滤（教学从简；生产把业务 seq 编码进
  条目 ID 或维护 seq→entry-id 索引做增量读，README 有说明）

### 实操：实验 r2
```bash
python r2_redis_stream/verify_replay.py
```
脚本自动起**两个真实进程**：A 创建任务跑完 → B（全新进程，RUNNING 为空）
回放完整事件流 → 再带 `Last-Event-ID: 3` 验证从 seq 4 补发。

### 代码流程讲解（r2_redis_stream/agent.py + app.py）
1. **AgentTask 变薄了**：没有 buffer，只有订阅者队列。emit = INCR 取号 → XADD 落库
   → put_nowait 给本进程订阅者。历史与实时开始分离。
2. **SSE 端点三段式升级**：XRANGE 回放（任何进程）→ 若任务在本进程则实时跟随 → 终态关流。
   注意 yield 风格 + Depends 404（learning-records/0002 的坑）。
3. **verify_replay.py 的断言**：B 进程回放 26 条事件、types[0]==agent_started、
   Last-Event-ID:3 → 首条补发 id==4。

### 自测
1. 为什么 seq 必须由 Redis INCR 保证，而不在 SSE 端点里现编？
2. 业务 seq 和 Stream 条目 ID 为什么是"不同轴"？各自适合做什么？
3. XRANGE 全量+过滤在什么事件量下会成为问题？

---

## L6.4 r3：Pub/Sub 广播 + 控制平面路由（毕业实验完全体）

### 目标
理解"数据面（Stream+Pub/Sub）与控制面（control 频道）"的分离设计；
跑通双进程端到端验证（暂停/恢复/审批全部跨进程生效）。

### 概念

**事件双写**：emit() = `XADD`（历史，必达可回放）+ `PUBLISH`（实时，广播可丢）。
不是二选一：实时性交给 Pub/Sub，可靠性交给 Stream——丢了的实时消息总能从 Stream 补回。

**控制平面的路由问题**（r3 最深的一课）：暂停闸门（asyncio.Event）和审批闸门
（Future）是**属主进程协程里的对象**，别的进程物理上碰不到。解法：
- 任何 Worker 的 WS 命令 → `PUBLISH agent:control:{id}`（不执行，只路由）
- **属主进程**的 control_listener 订阅该频道 → 收到命令落到本进程的闸门上
- 执行结果以 `task_state` 事件走数据面广播 → UI 无需专门的状态接口

**Pub/Sub 的两个生产陷阱**（verify 脚本里都有对策）：
1. 不留存消息：发布时订阅未就绪 → 消息消失。对策：客户端控制"重发直到看到状态反馈"。
2. 实时与持久必须配合：只靠 Pub/Sub 的系统，重启/断线就丢历史。

### 实操：实验 r3
```bash
# 两个终端各起一个 Worker
python -m uvicorn r3_redis_fanout.app:app --port 18901
python -m uvicorn r3_redis_fanout.app:app --port 18902
# 浏览器：18901 启动任务 → 18902 的任务列表里立刻可见（Hash）

# 自动化端到端（课程最重要的一条命令）：
python r3_redis_fanout/verify_multiworker.py
```
脚本起两个真实进程，断言四件事：
1. A 创建的任务 B 的任务列表可见（Hash）
2. B 发的 pause 经 control 频道 → A 的闸门生效（收到 task_state=paused）
3. B 的 approve → A 的审批 Future 被唤醒 → tool_result 出现
4. B 视角的 41 条事件 seq 单调，终态写回 Hash

### 代码流程讲解（r3_redis_fanout/）
1. **AgentTask 更薄了**：只有 emit（INCR+XADD+PUBLISH）。连接的订阅者队列也不需要了——
   见下一条。
2. **进程级 event_bridge**（app.py）：唯一一个协程 `psubscribe agent:events:*`，
   把收到的消息投给本进程的 LOCAL_QUEUES。SSE 端点只从本地队列取。
   为什么不让每个 SSE 连接自建 Pub/Sub 订阅？连接断建都要重建订阅、浪费连接、
   取消语义混乱——**进程级桥**是生产标准形态（v7 的 ControlHub 就是它的单进程版）。
3. **Runtime 收拢句柄**（agent.py）：runner、listener、controls 三个句柄互相要触达
   （listener 要 cancel runner；runner 结束要 cancel listener）——用一个小类收拢比
   散装全局变量清晰得多。
4. **控制命令的可靠性**：Pub/Sub 不留存，所以"发布即生效"是错觉；
   verify 的 send_until 用"重发直到看到状态反馈"——这也是真实 UI 的做法。

### 自测（labs/r3_redis_fanout/README.md 四题）
1. 暂停闸门能不能也搬进 Redis？为什么闸门必须在属主进程？
2. approve 重复发布为什么不会重复触发工具？（提示：Future.done() 守卫）
3. 画出从 emit 到浏览器的完整路径（跨两个 Worker）。
4. A 崩溃后运行中的任务怎么办？生产如何做"心跳+超时接管"？

### 延伸
- 把事件信封映射到 AG-UI 协议（RUN_STARTED/TEXT_MESSAGE_*），你的 r3 就能接标准前端。
- 事件量大了：XRANGE 全量+过滤 → 增量读；Stream 设 MAXLEN 防止无限增长。
