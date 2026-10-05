"""r1 事件模型：与 v6/v7 相同的统一信封（各实验独立目录、独立可运行）。"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    agent_started = "agent_started"
    agent_error = "agent_error"
    step_started = "step_started"
    step_finished = "step_finished"
    rag_search = "rag_search"
    rag_result = "rag_result"
    token = "token"
    done = "done"


class AgentEvent(BaseModel):
    seq: int
    type: EventType
    task_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: dict = Field(default_factory=dict)
