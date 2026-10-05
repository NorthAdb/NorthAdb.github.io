"""v7 的事件模型：与 v6 相同的统一信封（故意重复，让两个实验各自独立可运行）。

对比时注意：v7 新增了 agent_error 的 cancelled 语义（data.cancelled=True），
用于优雅表达"用户主动取消"——取消不是错误，但要作为终态事件广播。
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    agent_started = "agent_started"
    agent_finished = "agent_finished"
    agent_error = "agent_error"
    step_started = "step_started"
    step_finished = "step_finished"
    rag_search = "rag_search"
    rag_result = "rag_result"
    tool_call = "tool_call"
    tool_result = "tool_result"
    token = "token"
    done = "done"


class AgentEvent(BaseModel):
    seq: int
    type: EventType
    task_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    data: dict = Field(default_factory=dict)
