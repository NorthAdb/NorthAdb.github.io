# 排障附录：实验环境常见坑（Windows 优先）

> 按症状索引。遇到报错先来这里找，30 秒解决不了再问 /teach 会话。

## 环境与启动

**`ModuleNotFoundError: No module named 'v7_agent_server'`**
- 必须在 `labs/` 目录下运行 `python -m uvicorn v7_agent_server.app:app ...`（模块路径相对 labs/）。
- v5/v6/v7 内部用的是包内相对导入（`from .agent import ...`），不要试图 `python v7_agent_server/app.py` 直接运行。

**端口被占用 `error while attempting to bind on address ... only one usage`**
- 上一个实验服务还开着。找到并结束：`netstat -ano | findstr 8803` → `taskkill /PID <pid> /F`。
- v3 三个变体共用 8803，同时只能起一个。

**pip 装完还是 import 失败**
- 确认虚拟环境已激活（命令行前面有 `(.venv)`），且 pip 装进了 venv：`python -m pip list`。
- `labs/requirements.txt` 是唯一依赖清单；别全局安装。

**Windows 防火墙弹窗**
- uvicorn 只绑 127.0.0.1 时不会触发；如果绑了 0.0.0.0 会弹窗，选"取消"也能本地实验。

## curl / 客户端

**POST 中文 body 报 422 或 body 解析错误**
- Windows Git Bash 的 curl 可能按本地代码页发送中文。解决：body 用 ASCII，或用 httpx：
  `python -c "import httpx; print(httpx.post('http://127.0.0.1:8801/chat', json={'text': '中文'}).json())"`

**`curl -N` 看流式还是"一次性出全"**
- `-N` 只是关掉 curl 自己的缓冲。若响应被代理/网关缓冲，加 `-i` 看 `transfer-encoding: chunked` 是否存在；本地实验一般就是忘了 `-N`。

**SSE 事件"看得到 data 但事件不派发"**
- 报文少了分界空行（`\n\n`）。用 lessons/0002 的 SSE 格式实验室逐行核对。

## 浏览器

**sse_client.html 连不上（onerror，readyState=2）**
- 跨域：file:// 页面连 SSE 端点受 CORS 约束。v3 三个服务已加 `CORSMiddleware`；若你自己注释掉了中间件，这是预期现象（见 v3 README 的对照实验）。
- 服务端根本没起：先 `curl -N http://127.0.0.1:8803/events` 确认服务活着。

**EventSource 报 GET 405**
- `EventSource` 只能 GET。LLM 对话接口是 POST——用 fetch + ReadableStream（v5/index.html 有完整解析器）。

**WebSocket 连接失败**
- 检查协议：`ws://` 不是 `http://`；路径是 `/ws/chat` 不是 `/chat`。
- 服务端没调用 `accept()` 也会失败。

## v6 / v7 专属

**SSE 流收到 200 但随后断开，服务端报 `'coroutine' object is not iterable`**
- fastapi.sse 端点必须自身是 async generator（yield 风格）。`return EventSourceResponse(gen())` 会炸——这是学习记录 0002 的头号坑。

**想要 404 却拿到 200 然后流中断**
- 校验要放在 `Depends` 依赖里。generator 内 raise HTTPException 只能掐断已开始的 200 流。

**任务列表/事件为空（重启后）**
- v6/v7 的任务与事件在**进程内存**里，重启即清空。这不是 bug——正是模块 5 引入 Redis 的理由。
