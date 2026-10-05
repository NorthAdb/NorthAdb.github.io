# 模块 4：LLM 流式与 Agent 事件系统

> 4 课 · 实验 v5、v6、v7（毕业实验）· 目标：从"流 token"到"流过程"，最终交付可遥控的 Agent Server

> 配图：Agent 事件管道 [diagrams/04-agent-event-pipeline.html](../diagrams/04-agent-event-pipeline.html) · v7 双通道时序 [diagrams/05-agent-server-dual-channel.html](../diagrams/05-agent-server-dual-channel.html)
> 互动课：[lessons/0003 Agent 事件时间线浏览器](../lessons/0003-agent-event-explorer.html)（单步回放一次真实任务的事件流与界面变化）

---

## L4.1 LLM Token Streaming 全链路

### 目标
跑通 v5；画出 token 从 LLM 到用户眼睛的完整翻译链。

### 全链路（背下来）

```
LLM SDK（stream=True 的 chunk）        ← 事件的"源头"
    → async generator（yield 事件）
    → SSE 端点（ServerSentEvent）      ← 网络上的形态：event: token\ndata: ...\n\n
    → 浏览器（fetch + ReadableStream 解析 / EventSource）
    → 打字机效果
```

### 实操：实验 v5

```bash
python -m uvicorn v5_llm_stream.app:app --port 8805 --reload
```
1. 浏览器打开 `http://127.0.0.1:8805/`——同一个 mock LLM 两个按钮：非流式"转圈圈 2 秒" vs 流式打字机；
2. `curl -N -X POST .../chat/stream ...` 看原始 SSE，注意最后一个事件是裸的 `[DONE]`；
3. （可选）`export OPENAI_API_KEY=...` 后重启——**下游代码零改动**切换到真实 LLM。

### 代码流程讲解（v5_llm_stream/app.py）

1. `mock_stream` 与 `openai_stream` 产出**同一种东西**（ServerSentEvent 流）。端点函数只做选择 + 收尾 `[DONE]`。**换供应商 = 换 generator**，这是接口对齐的威力。
2. `raw_data="[DONE]"`：`data=` 会被 JSON 编码，`raw_data` 原样发送——LLM 协议里裸字符串哨兵（`[DONE]`）的专用通道。
3. index.html 里 30 行实现 SSE 解析器（fetch + ReadableStream）：因为 `EventSource` 只支持 GET，LLM 对话要 POST。**你在 v3a 手写过的格式，现在从客户端再认一遍**。

### 自测
1. token 从 LLM 到屏幕经过几次"翻译"？每次的输入输出？
2. 没有 `[DONE]`，客户端还能靠什么判断结束？（连接关闭——但显式哨兵能区分"正常结束"和"异常断开"）

---

## L4.2 统一 Agent 事件协议：对齐 AG-UI / Dify

### 目标
理解为什么"只传 token"不够；掌握统一事件信封设计；能把课程事件表与业界协议对照。

### 概念

Agent 的价值在**过程**：检索到了什么、调用了什么工具、为什么这么答。只流 token = 只直播结论。要把过程流出去，需要一个**事件协议**。设计三原则：

1. **信封一致**：所有事件同构 `{seq, type, task_id, timestamp, data}`——前端写一套分发逻辑通吃。
2. **三段式**：有开始就有结束（step_started/step_finished、tool_call/tool_result）——前端据此维护卡片状态机。
3. **单调 seq**：既是 SSE 的 `id`，又是断线续传位点、又是前端排序键。

### 事件对照表（读开源项目的钥匙）

| 本课程 | AG-UI | Dify (streaming) | LangChain |
|---|---|---|---|
| agent_started/finished/error | RUN_STARTED/FINISHED/ERROR | workflow_started/finished | on_chain_start/end |
| step_started/finished | STEP_STARTED/FINISHED | node_started/finished | on_chain_start/end |
| rag_search/rag_result | CUSTOM/STEP 携带 | node 事件（retriever 节点） | on_retriever_start/end |
| tool_call/tool_result | TOOL_CALL_START/RESULT | agent_thought | on_tool_start/end |
| token | TEXT_MESSAGE_CONTENT(delta) | message | on_chat_model_stream |
| done | RUN_FINISHED | message_end | — |

结构相似度极高——**学会这套，读任何 Agent 平台的事件流只是换名字**。AG-UI 还定义了课程未展开的进阶事件：STATE_SNAPSHOT/STATE_DELTA（JSON Patch 增量同步）、SUBAGENT_*、人工中断的 RUN_FINISHED(outcome=interrupt)——正是 v7 审批功能的协议化表达。

### 代码讲解（v6_agent_events/events.py）
`EventType` 枚举 + `AgentEvent` 信封（Pydantic）。注意 `seq` 由 Agent 侧生成（不是 SSE 端点现编）——因为断线重连后端点会换一个，但事件序列不能换。

---

## L4.3 事件流架构：Agent Runtime 与通信层解耦

### 目标
指出解耦边界；解释 v6 已知局限如何引出 v7 设计。

### 代码讲解（v6 agent.py + app.py）

- `FakeRAGAgent.run()` 是 async generator，只管 `yield AgentEvent`——**完全不知道 FastAPI/SSE 存在**。换 WS、写单测、做 CLI 版，都不动它。这就是解耦边界。
- `to_sse()` 是唯一知道"事件怎么变成网络字节"的函数（`event=type, id=seq, data=整个事件`）。
- `TASK_STORE` 边发边记 → replay 端点按 seq 补发。

### v6 的三个已知局限（刻意留下）
1. Agent 生成器与 SSE 连接**同生共死**——浏览器断开，generator 没人消费，任务中断（真实 Agent 不能这样死）。
2. 无控制能力：不能暂停/取消/审批。
3. 进程内存存储，多 Worker 即失效（M5 主题）。

### 自测
1. 为什么说"解耦点在 async generator 的 yield 边界"？
2. 如果要把 v6 的 token 事件改成走 WebSocket，哪些文件要动？（答案：只动 app.py——验证解耦是否真的成立）

---

## L4.4 毕业实验：双通道 Agent Server（v7）

### 目标
理解并复述 v7 的五个关键设计；跑通全部控制操作；完成断线续传实验。

### 实操

```bash
python -m uvicorn v7_agent_server.app:app --port 8807 --reload
```
浏览器打开 `http://127.0.0.1:8807/`，依次完成：
1. 启动任务 → 左侧打字机 + 右侧事件日志；
2. **审批**：中途弹出审批卡片 → 批准/拒绝各试一次；
3. **暂停/恢复**：观察暂停时代码停在哪个检查点；
4. **取消**：暂停后取消 → agent_error(cancelled) 优雅收尾；
5. **断线续传**：任务运行中刷新页面 → EventSource 自动重连，事件从断点继续，不重不漏；
6. 自动化验证：`python v7_agent_server/test_flow.py`（断言 29 条事件、seq 单调、审批成功）。

### 五个关键设计（对照 labs/v7_agent_server/README.md 的架构图）

1. **Agent 与连接解耦**：`asyncio.create_task(run_agent_task(task))` 后台运行（L1.1 演示 3 的落地）。浏览器关了任务照跑，重开页面从 buffer 续看。
2. **buffer + 订阅者队列**：`emit()` 同时写 buffer（全量日志，重放依据）和每个 SSE 订阅者的 Queue（实时分发）。SSE 端点三步走：**先订阅 → 再补历史 → 水位线去重**——不漏不重。
3. **暂停 = asyncio.Event 闸门**：agent 每步之间 `await task.checkpoint()`。pause 清信号 → 协程挂在闸门上；resume 置信号 → 从原位继续。没有轮询。
4. **审批 = asyncio.Future**：`wait_approval()` 挂在一个 Future 上；WS 收到 approve/reject 后 `set_result()` 唤醒。**human-in-the-loop 的本质：把一次 await 的答案交给人类来填**。
5. **取消 = task.cancel()**：CancelledError 在最近的 await 点抛出，被主流程捕获 → 发 agent_error 事件优雅收尾。用户看到的是一条事件，不是崩溃。

### 双通道分工（本课程核心结论）

```
SSE   GET /agent/tasks/{id}/events   Agent → UI   单向直播、断线续传、过代理
WS    /ws/control                    UI → Agent   实时控制 + 状态镜像（approval_required、state_update）
```
WS 的 ControlHub 把状态变化镜像推给所有控制连接——它就是 M5 里 Redis Pub/Sub 的"单进程预演"。

### 自测（labs/v7_agent_server/README.md 5 题）
必须能口头回答第 1、3、4 题（订阅顺序 / 暂停后取消的事件顺序 / 为什么审批走 WS 而测试的 SSE 只读）。

### 延伸
- 把 mock 换成真 LLM + 真 RAG：`agent.py` 的 `run_agent_task` 换成你 M4 之前写的 Agent，事件 emit 点不变——通信层完全复用。
