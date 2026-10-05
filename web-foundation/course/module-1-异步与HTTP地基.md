# 模块 1：地基——异步与 HTTP

> 4 课 · 实验 A1、v0 · 目标：理解"服务器同时服务很多人"靠什么，看懂 HTTP 报文，跑通第一个 FastAPI

---

## L1.1 Python 异步：SSE/WebSocket 的前置知识

### 目标
1. 说清楚"阻塞"为什么是 Web 服务的天敌；2. 理解 `await` 时刻发生了什么；3. 认识 Task 与 Queue 这两个后续反复出现的角色。

### 概念

**为什么需要 async**：一个 HTTP 请求的大部分时间其实在做 IO（等数据库、等 LLM 返回）。同步模型下，一个 worker 在等待时干不了别的——1000 个并发用户就需要 1000 个 worker（线程）。异步模型下，worker 在 `await` 的瞬间**把执行权交还给事件循环**，事件循环去推进别人。一个进程就能扛住成千上万的连接。

三个关键词：
- **协程（coroutine）**：`async def` 定义的函数，可以"暂停/继续"。
- **事件循环（event loop）**：调度器，谁在 `await`，它就把 CPU 给别人。
- **`await`**：不是"开新线程"，是"我先挂起，好了叫我"。

### 实操：实验 A1（labs/a1_async）

```bash
python a1_async/asyncio_basics.py
```

### 代码流程讲解（asyncio_basics.py）

1. **演示 1（串行阻塞）**：`time.sleep(1)` 是同步阻塞——虽然函数是 `async def`，但它睡死在事件循环上，两个任务总耗时 2 秒。**教训：async 函数里混用同步阻塞，并发就是假的**（LLM 开发里最常见事故：在 async 端点里调了同步 SDK）。
2. **演示 2（gather 并发）**：三个 `fetch` 各睡 1 秒，`asyncio.gather` 总耗时 ≈1 秒。每个 `await asyncio.sleep` 挂起的瞬间，事件循环去推进另一个协程。
3. **演示 3（create_task）**：`asyncio.create_task(long_job())` 提交后台任务后**立刻返回**——这正是 v7 里 Agent 任务与 HTTP 请求解耦的机制。
4. **演示 4（Queue 生产者/消费者）**：生产者放事件、消费者取事件，`None` 哨兵表示结束。把"生产者"换成 Agent、把"消费者"换成 SSE 连接，就是 M4 的全部架构图。

### 自测

1. `await asyncio.sleep(1)` 和 `time.sleep(1)` 在 async 函数里的本质区别？
2. 为什么演示 4 的模型"对 SSE、Agent 事件都重要"？
3. `create_task` 创建的任务如果没人 `await`，程序退出时会怎样？

### 常见坑

- 在 `async def` 端点里调用同步阻塞库（requests、同步 openai SDK）→ 整个服务卡死。解法：用异步版 SDK，或 `run_in_executor`。
- 以为 async = 多线程。单线程、单进程、协作式调度。

---

## L1.2 HTTP 报文解剖

### 目标
能用 `curl -i` 指出请求/响应的三段结构，说出常用状态码的语义。

### 概念

一个 HTTP 响应的完整结构（curl -i 会展示前两段）：
```
HTTP/1.1 200 OK          ← ① 状态行：协议版本 + 状态码 + 短语
content-type: application/json    ← ② Headers：元信息（类型、长度、缓存…）
content-length: 25

{"message":"hello"}      ← ③ Body：载荷
```

请求同理：`请求行（GET /hello HTTP/1.1）+ Headers + Body`。

必背状态码（结合 Agent 场景记忆）：
- 200 成功；201 已创建（POST 建任务成功）
- 400 参数格式坏；401 未认证；403 无权限；404 不存在；409 冲突；422 校验失败（FastAPI 的 Pydantic 拒绝时就是它）；429 限流（LLM 网关常见）；500 服务器内部错误；502/504 网关错（Nginx 后面挂了/超时——流式课程里你会经常见到它）

### 实操

```bash
curl -i http://127.0.0.1:8801/hello          # 观察响应三段
curl -i http://127.0.0.1:8801/not-exist      # 404 长什么样
curl -i -X POST http://127.0.0.1:8801/chat -H "Content-Type: application/json" -d '{"tex": "typo"}'   # 422
```
浏览器 F12 → Network → 任选一个请求 → 逐栏对照 Headers / Payload / Response。
工具链：`curl`（看原始字节）、`httpx`（Python 客户端，写测试）、Postman/Insomnia（图形界面）。

### 自测

1. 401 和 403 差在哪？422 和 400 呢？
2. `content-type: application/json` 是告诉谁的？
3. 504 最可能出在你架构图的哪条线上？

---

## L1.3 Keep-Alive 与长连接

### 目标
理解"连接复用"如何发生，为"连接可以一直开着传数据"（流式/WS）铺路。

### 概念

HTTP/1.0 时代：每个请求都要 TCP 三次握手 → 传数据 → 挥手，一个网页 20 张图 = 20 次握手。
HTTP/1.1 起默认 **Keep-Alive**：一条 TCP 连接上传完一个请求/响应**不关闭**，下一个请求接着用。
```
请求1 → 响应1 → 请求2 → 响应2 → …（同一条 TCP 连接）
```
关键认知升级：**HTTP 协议本身没有"连接必须即用即关"的规定**。Keep-Alive 之后，"连接"与"请求"解耦了。那么——
- 如果服务器传完响应 1 的"一半"就停住，让 Body 慢慢传呢？→ 这就是**流式**（M2）
- 如果干脆换掉这条连接上的协议呢？→ 这就是 **WebSocket Upgrade**（M3）

### 自测

1. Keep-Alive 解决了什么浪费？
2. "HTTP 只能一问一答"这个说法精确吗？哪里不精确？

---

## L1.4 第一个 FastAPI：路由、Pydantic、OpenAPI

### 目标
跑通 v0，理解"函数签名即接口契约"，会用 /docs 和 F12 调试。

### 概念

FastAPI 的核心思想：**你写带类型注解的 Python 函数，框架负责把 HTTP 世界翻译成 Python 世界**。
```
URL / 方法      → 路由装饰器（@app.get/@app.post）
Query/Body/Header → 函数参数（自动解析+校验）
返回值          → 自动 JSON 序列化
类型注解        → 自动生成 OpenAPI 文档（/docs 网页）
```

### 实操：实验 v0

```bash
python -m uvicorn v0_hello_api.app:app --port 8801 --reload
```
按 labs/v0_hello_api/README.md 的清单逐条做（含故意制造 422、浏览 /docs、F12 观察）。

### 代码流程讲解（v0_hello_api/app.py）

1. `@app.get("/hello")`：框架内部维护一张路由表 `（方法, 路径) → 函数`。请求到达时查表、解析参数、调用函数、序列化返回值。
2. `name: str = "world"`：从 `?name=xxx` 提取并做类型转换；类型不符自动 422。
3. `ChatRequest(BaseModel)`：POST body 先过 Pydantic 校验再进函数——**脏数据进不了你的业务逻辑**。这在流式接口里同样适用（M4 的 Prompt 模型）。
4. `async def`：协程跑在事件循环上——L1.1 的知识在这里落地。uvicorn 是**运行这些协程的 ASGI 服务器**（M2 讲它和 FastAPI 的分工）。

### 自测

见 labs/v0_hello_api/README.md 末尾 4 题。全答对即可进入 M2。

### 常见坑

- Windows Git Bash 下 curl `-d` 写中文可能被编码搞坏 → 用 ASCII 或 httpx（README 有说明）。
- `--reload` 只用于开发；它通过监视文件重启进程，生产禁用。
