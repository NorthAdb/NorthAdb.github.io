# v7 毕业实验：Mini Agent Server

目标：把前面所有实验组装成一个完整产品形态——**SSE 直播 Agent 过程，WebSocket 遥控 Agent 行为**，包括人工审批（human-in-the-loop）。

## 启动与观察

```bash
python -m uvicorn v7_agent_server.app:app --port 8807 --reload
```

1. 浏览器打开 `http://127.0.0.1:8807/`，点"启动任务"：
   - 左侧：回答逐字出现；中途弹出**审批卡片** → 批准后流程继续；
   - 右侧控制台：随时暂停/恢复/取消，状态胶囊实时变化；
   - 底部：SSE 全量事件日志。
2. **断线续传实验**：任务运行中刷新页面（或 F12 断网 3 秒）→ EventSource 自动重连，事件从断点继续，不重不漏。
3. **暂停实验**：暂停后取消 → 观察 agent_error(cancelled) 事件优雅收尾。
4. 自动化验证：`python v7_agent_server/test_flow.py`（保持服务运行）。

## 架构讲解

```
浏览器 UI
  │ POST /agent/tasks            创建任务（REST）
  │ GET  /agent/tasks/{id}/events  ← SSE：事件直播 + Last-Event-ID 续传
  └ WS   /ws/control              ← WebSocket：pause/resume/cancel/approve/reject
                                      + 状态镜像（state_update / approval_required）
FastAPI
  ├─ AgentTask（agent.py）
  │    buffer（全量事件日志）+ 订阅者队列（SSE 连接在这里等事件）
  │    控制原语：_resume Event（暂停闸门）｜approval Future（审批闸门）｜runner.cancel()（取消）
  └─ ControlHub：把状态变化镜像推给所有 WS 控制连接
```

### 五个关键设计（对照代码）

1. **Agent 与连接解耦**（app.py `create_task`）：`asyncio.create_task(run_agent_task(task))` 启动后台任务。浏览器关掉，任务照跑；重新打开页面，从 buffer 续看。这就是 v6 局限的解法。
2. **双层数据结构**（agent.py `emit`）：buffer 存全量（重放依据），每个 SSE 订阅者一个 Queue（实时分发）。`task_events` 端点"先订阅、再补历史、重叠去重"，保证不漏不重。
3. **暂停 = Event 闸门**：agent 在每个步骤间 `await task.checkpoint()`。pause 清除 Event 信号 → 协程挂起在闸门；resume 设置信号 → 从原位继续。**没有轮询**。
4. **审批 = Future**：`wait_approval()` 挂起在一个 Future 上，WebSocket 收到 approve/reject 后 `set_result()` 唤醒它。human-in-the-loop 的本质是"把一次 await 的结果交给人类来填"。
5. **取消 = task.cancel()**：CancelledError 在最近的 await 点抛出，被主流程捕获后发出 agent_error 事件优雅收尾——用户看到的不是崩溃，而是一条事件。

## 自测问题

1. SSE 订阅者为什么要"先订阅队列，再补发 buffer"？反过来会怎样？
2. 如果两个浏览器同时订阅同一任务，各能收到全量事件吗？代码里哪一行保证了这一点？
3. pause 期间用户点了 cancel，事件顺序是什么？（提示：CancelledError 抛在 checkpoint 的 wait() 上）
4. ControlHub 的广播在多 Worker 部署下会失效吗？为什么？（v8 主题）
5. test_flow.py 里 SSE 消费者为什么不发 approve，而是另开 WS 连接发？（提示：关注点分离）

## 延伸

- 模块 5：把单进程的 buffer/Hub 换成 Redis，把服务搬进 Nginx/Docker 之后会发生什么。
