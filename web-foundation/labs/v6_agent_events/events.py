"""v6：统一 Agent 事件协议——本课程对齐 AG-UI / Dify 的最小事件模型。

设计原则（详见 module-4 课程文档）：
1. 信封一致：所有事件同构 {seq, type, task_id, timestamp, data}，前端只写一套处理逻辑
2. 三段式：有"开始"的事件就有对应的"结束"（step_started/step_finished，tool_call/tool_result）
3. 单调 seq：既是 SSE 的 id，也是断线续传的位点（对齐 AG-UI 的顺序保证）
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    # 生命周期（AG-UI: RUN_STARTED / RUN_FINISHED / RUN_ERROR；Dify: workflow_started/finished）
    agent_started = "agent_started"
    agent_finished = "agent_finished"
    agent_error = "agent_error"
    # 步骤（AG-UI: STEP_STARTED / STEP_FINISHED；Dify: node_started/node_finished）
    step_started = "step_started"
    step_finished = "step_finished"
    # RAG 过程事件（自造名，语义对齐 Dify 的 node_started 携带检索信息）
    rag_search = "rag_search"
    rag_result = "rag_result"
    # 工具（AG-UI: TOOL_CALL_START / TOOL_CALL_RESULT）
    tool_call = "tool_call"
    tool_result = "tool_result"
    # 文本流（AG-UI: TEXT_MESSAGE_CONTENT 的 delta）
    token = "token"
    # 终态
    done = "done"


class AgentEvent(BaseModel):
    """统一事件信封：SSE 里 event=type, id=seq, data=整个事件 JSON。"""

    seq: int                                  # 全局单调递增，断线续传的位点
    type: EventType
    task_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    data: dict = Field(default_factory=dict)  # 各事件专属载荷
