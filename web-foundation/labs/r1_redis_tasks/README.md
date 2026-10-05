# r1 · 任务表外移到 Redis Hash

目标：解决 v7 留下的第一个局限——`TASKS` 字典只存在于创建任务的那个进程里。
外移后，**任何进程、任何连接**都能读到任务状态。

## 版本说明（先读）

- 本实验用 Docker 官方镜像 **`redis:7-alpine`**（`docker run -d --name course-redis -p 6399:6379 redis:7-alpine`）。
- 为什么是 7.x：官方 Redis 不支持 Windows 原生运行，Docker/Linux 上的 7.x/8.x 是生产标准。
  课程只使用 Hash / Stream / Pub/Sub——这些原语从 4.0 起行为一致，你在任何版本上运行结论相同。
- 代码里的 `get_redis()` 读 `REDIS_URL` 环境变量：换成公司内网的 Redis、云 Redis、
  任何 7.x/8.x 实例，实验代码零改动。连不上时会降级到 fakeredis（单进程仿真），
  让你至少能把流程跑通——但 r3 的多进程验证必须真 Redis。
- 用了 Redis 7 的 RESP3 协议（redis-py 默认启用）：旧 Windows 移植版 Redis 5 不支持 `HELLO`，
  这也是"用官方镜像"的理由之一。

## 启动与观察

```bash
# 终端 1：服务（labs/ 目录下）
python -m uvicorn r1_redis_tasks.app:app --port 18901

# 终端 2：创建任务并查看
curl -X POST http://127.0.0.1:18901/agent/tasks -H "Content-Type: application/json" -d '{"goal": "r1 demo"}'
curl http://127.0.0.1:18901/agent/tasks

# 终端 3：绕过 HTTP，直接看 Redis 里存了什么（等于"另一个进程"在看）
docker exec course-redis redis-cli hgetall agent:tasks
python r1_redis_tasks/verify_cross_connection.py
```

对照 v7：当时 `curl http://其他进程/agent/tasks` 要么 404 要么看不到别的进程创建的任务；
现在任何连接都能看到——因为状态在 Redis，不在进程内存。

## 代码流程讲解

1. **`TaskStore`（app.py）**：四个方法 create/get/set_state/all，每个方法就是一条 Redis 命令
   （`HSET` / `HGET` / `HSET` / `HVALS`）。注意它不知道 FastAPI 的存在——这就是适配层：
   v7 里所有 `TASKS[...]` 的读写点换成 `STORE.xxx`，其余逻辑一行没动。
2. **`agent.py` 刻意没变**：事件缓冲 buffer、订阅者队列仍是内存。`run_agent_task` 在生命周期
   临界点调用 `store.set_state()`（done/cancelled/error），让 Hash 里的状态始终可信。
3. **`RUNNING.pop(task_id)`**（agent.py finally 块）：任务结束后从进程登记簿移除——
   进程内只保留"活着的东西"，历史数据靠 r2 的 Redis Stream。

## r1 结束后还剩两个局限（r2/r3 的伏笔）

- 事件流仍在内存：换进程看不到事件，断线续传跨进程不成立 → **r2 Stream**
- 后台任务在进程内：控制指令（暂停/审批）无法跨进程送达属主 → **r3 Pub/Sub + 控制通道**

## 自测问题

1. `HSET agent:tasks <id> <json>` 与 v7 的 `TASKS[id] = {...}` 差别在哪一层？对调用方可见吗？
2. 为什么 `RUNNING` 登记簿不能搬进 Redis？（提示：它存的是 asyncio.Task 句柄）
3. 服务的哪个端点在 r1 仍是"进程绑定"的？为什么？
