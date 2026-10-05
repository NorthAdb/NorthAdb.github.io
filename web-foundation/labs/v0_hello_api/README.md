# v0 Hello API

目标：让"HTTP 请求 → FastAPI 函数 → HTTP 响应"这条最基本的链路在你手里跑通。

## 启动

```bash
cd labs
python -m uvicorn v0_hello_api.app:app --port 8801 --reload
```

## 实操清单（逐条做，观察现象）

1. `curl -i http://127.0.0.1:8801/hello`
   → 找到响应里的三段：状态行 `HTTP/1.1 200 OK`、Headers（`content-type: application/json`）、Body。
2. `curl "http://127.0.0.1:8801/hello?name=Agent"` → 查询参数进函数参数。
3. `curl -X POST http://127.0.0.1:8801/chat -H "Content-Type: application/json" -d '{"text": "hello rag"}'`
   > Windows Git Bash 提示：`-d` 里直接写中文可能因终端编码被 curl 搞坏（服务端会报 body 解析错误）。
   > 用 ASCII 文本测试，或改用 `python -c "import httpx; print(httpx.post('http://127.0.0.1:8801/chat', json={'text': '什么是RAG'}).json())"`。
4. 故意发错：`-d '{"tex": "typo"}'` → 观察 **422** 和错误详情，这就是 Pydantic 校验。
5. 浏览器打开 `http://127.0.0.1:8801/docs` → FastAPI 由类型注解自动生成的 OpenAPI 文档。
6. 浏览器 F12 → Network → 重新请求 → 点开 Request/Response 看 Headers 与 Payload（以后调试 SSE/WS 全靠这个面板）。

## 代码流程讲解（app.py）

1. `@app.get("/hello")` —— 装饰器注册路由表：`GET /hello` → `hello()`。FastAPI 本质就是一张"请求特征 → 处理函数"的映射表。
2. `name: str = "world"` —— 函数签名即接口契约：FastAPI 从中提取查询参数并做类型转换。
3. `ChatRequest(BaseModel)` —— 请求体反序列化 + 校验。失败 → 422，你的函数根本不会被调用。
4. `async def` —— 处理函数是协程，运行在事件循环上；遇到 IO 会 `await` 让出执行权（模块 1 的知识在这里落地）。
5. 返回值 —— FastAPI 用 `jsonable_encoder` 序列化成 JSON 写回响应体。

## 自测问题

1. GET 的参数从哪里来？POST 的呢？
2. 422 和 404 分别是什么弄错了？
3. `--reload` 干什么的？为什么生产环境不开？
4. `/docs` 页面背后是什么规范在起作用？

## 延伸

- FastAPI 官方教程第一页：https://fastapi.tiangolo.com/zh/tutorial/
