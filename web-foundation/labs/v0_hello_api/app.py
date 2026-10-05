"""实验 v0：第一个 FastAPI 服务——一切通信实验的起点。

启动：python -m uvicorn v0_hello_api.app:app --port 8801 --reload
（在 labs/ 目录下运行；--reload 表示改代码自动重启，仅开发时用）

验证：
  curl http://127.0.0.1:8801/hello
  curl "http://127.0.0.1:8801/hello?name=Agent"
  curl -X POST http://127.0.0.1:8801/chat -H "Content-Type: application/json" -d '{"text": "什么是 RAG"}'
  curl http://127.0.0.1:8801/docs        # 浏览器打开，看自动生成的 API 文档
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="v0 Hello API", version="0.0.1")


# ---------- 路由：把 HTTP 请求映射到 Python 函数 ----------


@app.get("/hello")
async def hello(name: str = "world") -> dict:
    """GET 请求：参数来自 URL 查询串 ?name=xxx，返回值自动序列化为 JSON。"""
    return {"message": f"hello, {name}"}


# ---------- Pydantic：请求体的类型与校验 ----------


class ChatRequest(BaseModel):
    """客户端 POST 上来的 JSON 会被自动解析成这个对象；字段对不上会返回 422。"""

    text: str
    lang: str = "zh"  # 有默认值 → 可选字段


class ChatReply(BaseModel):
    reply: str
    echo: str


@app.post("/chat", response_model=ChatReply)
async def chat(req: ChatRequest) -> ChatReply:
    """POST 请求：请求体 JSON → Pydantic 校验 → Python 对象 → 业务逻辑。"""
    return ChatReply(reply=f"你说的是：{req.text}", echo=req.text)


# ---------- 自己动手试的坑位 ----------


@app.get("/tasks/{task_id}")
async def get_task(task_id: int) -> dict:
    """路径参数：/tasks/123 中 123 会被解析成 int；传非数字 FastAPI 直接回 422。"""
    return {"task_id": task_id, "status": "fake"}
