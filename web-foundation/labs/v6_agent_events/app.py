"""实验 v6：把 Agent 内部事件接到 SSE——"流文本"升级为"流过程"。

启动：python -m uvicorn v6_agent_events.app:app --port 8806 --reload
观察：
  curl -N -X POST http://127.0.0.1:8806/agent/run -H "Content-Type: application/json" -d '{"question": "什么是RAG"}'
  # 你会看到 agent_started → rag_search → rag_result → tool_call → tool_result
  # → 一串 token → done 的完整事件时间线，每个事件都带单调递增的 id。

  # 任务跑完后，可按位重放（断线重连的雏形）：
  curl -N "http://127.0.0.1:8806/agent/tasks/<task_id>/replay?after=3"

两个 fastapi.sse 工程要点（踩坑实录）：
  1. 端点函数必须自身是 async generator（yield 风格）
  2. 404 等错误语义放进 Depends 依赖——依赖在响应开始前执行，
     在 generator 里 raise 只会把 200 响应流中途掐断
"""

import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from .agent import FakeRAGAgent
from .events import AgentEvent

app = FastAPI(title="v6 Agent 事件流")

agent = FakeRAGAgent()

# 任务事件缓冲：task_id -> 事件列表。生产中放 Redis/数据库，这里内存演示。
TASK_STORE: dict[str, list[AgentEvent]] = {}


def to_sse(ev: AgentEvent) -> ServerSentEvent:
    """统一信封 → SSE 字段：event=事件类型，id=序号，data=完整事件 JSON。
    mode="json" 让 Pydantic 把枚举/时间转成可 JSON 序列化的原始类型。"""
    return ServerSentEvent(event=ev.type.value, id=str(ev.seq), data=ev.model_dump(mode="json"))


class RunRequest(BaseModel):
    question: str


@app.post("/agent/run", response_class=EventSourceResponse)
async def run_agent(req: RunRequest):
    """发起一次 Agent 运行，响应用 SSE 直播全过程（对齐 Dify streaming / OpenAI Responses）。"""
    task_id = uuid.uuid4().hex[:8]
    buffer = TASK_STORE.setdefault(task_id, [])
    async for ev in agent.run(task_id, req.question):
        buffer.append(ev)  # 一边发一边记：为重放留证据
        yield to_sse(ev)


def _get_buffer(task_id: str) -> list[AgentEvent]:
    """依赖：校验在响应开始前发生，404 能正常返回。"""
    if task_id not in TASK_STORE:
        raise HTTPException(status_code=404, detail="task not found")
    return TASK_STORE[task_id]


@app.get("/agent/tasks/{task_id}/replay", response_class=EventSourceResponse)
async def replay(after: int = 0, buffer: list[AgentEvent] = Depends(_get_buffer)):
    """重放某个任务 seq > after 的事件（v7 会把它与 Last-Event-ID 自动续传打通）。"""
    for ev in buffer:
        if ev.seq > after:
            yield to_sse(ev)
