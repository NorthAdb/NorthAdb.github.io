# 模块 0：为什么 Agent 开发者需要网络通信

> 2 课 · 无实验要求 · 目标：建立"通信层"的心智位置，知道这门课每一站为什么存在

---

## L0.1 三种通信模型：一问一答、单向直播、双向对话

### 目标
不看资料说出三种模型的区别，并能各举一个 Agent 场景的例子。

### 概念（初学者视角）

把服务器想象成一家餐厅：

| 模型 | 餐厅比喻 | 技术名 | Agent 场景 |
|---|---|---|---|
| 一问一答 | 你点一道菜，厨师做完端上来，你吃完再点下一道 | 普通 HTTP API | 提交一个 RAG 查询，等完整结果 |
| 单向直播 | 厨师边做边喊："菜洗好了→下锅了→起锅了" | SSE（Server-Sent Events） | LLM 逐 token 输出、RAG 检索进度、工具调用日志 |
| 双向对话 | 你和厨师边做边聊："少放辣""好""等等，先别放盐" | WebSocket | 用户随时打断 Agent、审批工具调用 |

关键直觉：**SSE 和 WebSocket 不是"更厉害的 HTTP"，而是解决了"HTTP 是一问一答"这个限制的两种姿势**——SSE 复用 HTTP 做"服务器一直说"，WebSocket 干脆升级协议做"双方一直说"。

### 动手观察（10 分钟）

在 labs 环境下分别体验三种模型（v2/v3b 服务已在模块 2 详细讲，这里先建立体感）：

```bash
# 一问一答：命令停在那里，直到完整结果出现
curl http://127.0.0.1:8801/hello

# 单向直播：数字一个一个蹦出来（连接一直开着）
curl -N http://127.0.0.1:8802/stream

# 双向对话：用 labs/v4_websocket/chat.html 开两个标签页互发消息
```

观察点：`curl -N` 时终端不是"等一下然后全出来"，而是**持续有内容到达**——这就是"长连接"的体感。

### 自测

1. 你的 RAG 问答页面想显示"正在检索知识库…"，哪种模型能做到？
2. 用户想随时点"停止生成"，哪种模型才能把这条指令传回服务器？
3. 三种模型里，哪种的浏览器端 API 是 `EventSource`？

### 常见坑

- 以为 SSE 是新协议——它是**纯 HTTP**，只是约定了响应体格式和浏览器行为。
- 以为 WebSocket 更快所以全用 WebSocket——它复杂得多（握手、状态、扩容），SSE 能做的不要上 WS。

---

## L0.2 全景地图：通信层在哪里遇见你的 Agent

### 目标
能对照全景架构图，指出"我已经会的"和"这门课要教的"分别在哪一层。

### 概念

你已经学的（Agent 内部）：
```
Agent Loop ── Tool Calling ── RAG ── Memory      ← 这是"发动机"
```
这门课要学的（Agent 对外）：
```
HTTP ── Streaming ── SSE ── WebSocket ── FastAPI ── ASGI    ← 这是"方向盘、仪表盘、油门"
```

两者相遇的接口是一条**事件流**（Event Stream）：
```
Agent Runtime  ──产出事件──▶  通信层  ──SSE/WS──▶  浏览器
（我在检索… / 我要调用工具… / 这是第 3 个 token / 我做完了）
```

打开全景架构图 [../diagrams/01-agent-server-architecture.html](../diagrams/01-agent-server-architecture.html)，从上往下过一遍：
Browser → Nginx → FastAPI → Agent Runtime（内含 LLM/RAG/Tool）→ Redis/PostgreSQL。
模块 0 你只需要记住**箭头的方向和含义**，每一层为什么存在会在后续模块逐一拆开。

### 自测

1. "Agent Runtime 与通信层解耦"——解耦点大致在哪个函数边界？（提示：M4 会给出精确答案：async generator）
2. 为什么说"Agent 产品化时，通信层不是 Agent 本身，但缺了它产品就存在不了"？

### 延伸

- 原始路线图的第 27/28 节（最终认知框架 / 与 Agent Harness 的联系）值得重读一遍——本课程就是它的落地版。
