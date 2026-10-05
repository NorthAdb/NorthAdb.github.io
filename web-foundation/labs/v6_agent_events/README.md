# v6 统一 Agent 事件流

目标：从"给前端传 token"升级为"给前端直播 Agent 的全过程"，并用可对齐业界的事件协议表达。

## 启动与观察

```bash
python -m uvicorn v6_agent_events.app:app --port 8806 --reload
curl -N -X POST http://127.0.0.1:8806/agent/run \
  -H "Content-Type: application/json" -d '{"question": "什么是RAG"}'
```

你会看到一条完整的事件时间线（SSE）：

```
event: agent_started  id: 1
event: step_started   id: 2    data: {"name": "rag_retrieve"}
event: rag_search     id: 3
event: rag_result     id: 4    data: {"documents": [...]}
event: step_finished  id: 5
event: tool_call      id: 6    data: {"tool": "calculator", ...}
event: tool_result    id: 7
event: step_started   id: 8    data: {"name": "generate"}
event: token          id: 9..n data: {"text": "检"}
event: done           id: n+1
```

任务跑完后再试重放：`curl -N "http://127.0.0.1:8806/agent/tasks/<task_id>/replay?after=3"`。

## 事件协议对照表（教学重点）

| 本课程 | AG-UI 协议 | Dify（streaming） | LangChain (astream_events) |
|---|---|---|---|
| `agent_started/finished/error` | `RUN_STARTED/FINISHED/ERROR` | `workflow_started/finished` | `on_chain_start/end` |
| `step_started/finished` | `STEP_STARTED/FINISHED` | `node_started/finished` | `on_chain_start/end` |
| `rag_search/rag_result` | （CUSTOM 或 STEP 携带） | `node_started`（节点类型 retriever） | `on_retriever_start/end` |
| `tool_call/tool_result` | `TOOL_CALL_START/RESULT` | `agent_thought` | `on_tool_start/end` |
| `token` | `TEXT_MESSAGE_CONTENT(delta)` | `message`（含 answer） | `on_chat_model_stream` |
| `done` | `RUN_FINISHED` | `message_end` | — |

读法：**结构相似度极高**。学会本课程这套，读 Dify / AG-UI / LangChain 的事件流源码只是换名字。

## 代码流程讲解

1. **events.py**：`AgentEvent` 是统一信封。`seq` 单调递增——它同时是 SSE 的 `id:`、重放位点、前端排序键。三段式配对（started/finished、call/result）让前端可以维护"打开的卡片"状态。
2. **agent.py**：`run()` 是 async generator，只管 yield 事件，完全不知道 FastAPI/SSE 的存在。**Agent Runtime 与通信层的解耦点就在这里**——以后要换 WebSocket、写测试、做 CLI 版 Agent，都不用动它。
3. **app.py**：`to_sse()` 把信封装进 SSE 字段；`TASK_STORE` 边发边记，replay 端点按 `seq` 补发。

## 已知局限（v7 要解决的）

- 断线后**运行中**的任务无法续传：SSE 断了，generator 也没人消费了（agent 与连接同生共死）。
- 没有任何控制能力：不能暂停、取消、审批。
- 单进程内存存储，多 Worker 无法共享事件。

## 自测问题

1. 为什么 `seq` 要由 Agent 侧生成，而不是 SSE 端点现编？
2. 三段式事件对前端有什么好处？（提示：tool 卡片从 START 到 RESULT 的状态机）
3. "Agent 与通信层解耦"具体指哪个函数边界？这样解耦后能做哪些事？

## 延伸

- AG-UI events 文档；Dify Send Chat Message（streaming）事件表。
