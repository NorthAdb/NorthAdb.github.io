# 从 HTTP 到实时 Agent Server

> 一门面向 **已入门 Agent/RAG 开发者** 的网络通信实战课程：
> 用 8 个模块、27 节课、16 个可运行实验，把一个 Python 进程里的 Agent，
> 一步步升级为 **能被浏览器访问、能流式输出、能被实时控制、可水平扩展** 的生产级服务。

```
浏览器 ──SSE(事件直播)+WebSocket(遥控)──▶ Nginx ──▶ Worker×2 ──▶ Redis ──▶ LLM/RAG
```

这门课的一切代码都**真实可跑**：16 个实验全部配备自动化端到端验证，
一条命令 `python labs/smoke_test.py` 即可回归全部实验（当前 14/14 通过）。

---

## 为什么有这门课

学完 Agent 基础（loop、tool calling）和 RAG 之后，这些能力还困在一个 Python 进程里：
用户无法打开网页提问、看不到答案逐字生成、无法中途打断或审批一次危险操作。

这门课只教一件事——**把 Agent 接到网络上**，沿着这条主线层层递进：

```
Python 异步 → HTTP → FastAPI → 流式传输 → SSE → WebSocket
→ LLM Token 流 → Agent 事件协议 → 多进程扩展(Redis) → 反向代理(Nginx)
```

每一层都遵循同一个学习闭环：**读概念 → 跑最小实验 → 亲手制造生产事故 → 修复它 → 自动化验证**。

## 课程总览（8 模块 / 27 课 / 16 实验）

| 模块 | 主题 | 实验 | 你将获得 |
|---|---|---|---|
| M0 | 为什么 Agent 开发者需要网络通信 | 观察实验 | 三种通信模型的心智地图 |
| M1 | 异步与 HTTP 地基 | A1, v0 | 事件循环直觉 + 第一个 FastAPI |
| M2 | 流式传输与 SSE | v2, v3a/b/c | 手写 SSE 报文 → 生产级实现 → 断线续传 |
| M3 | WebSocket 双向通信 | v4 | 握手/帧/广播/ConnectionManager |
| M4 | LLM 流式与 Agent 事件系统 | v5, v6, v7 | token 打字机 + 统一事件协议 + 双通道 Agent Server |
| M5 | 综合项目与生产化 | v8 | 生产化设计清单 |
| M6 | 生产基础设施 I · Redis 事件总线 | r1/r2/r3 | Hash/Stream/Pub/Sub 三原语外移，多进程完全体 |
| M7 | 生产基础设施 II · Nginx 与部署 | n1/n2 | 反代三组生死配置 + 完整拓扑总装 |

详细讲义在 [`course/` 模块讲义](course/module-0-为什么需要网络通信.md)（27 节课，每节含目标/概念/实操/代码流程讲解/自测题/常见坑）。

## 快速开始

### 环境要求

- Python 3.10+（建议 3.12）
- Docker Desktop（Redis 与 Nginx 以官方镜像运行：`redis:7-alpine`、`nginx:1.28-alpine`）
- 可选：`OPENAI_API_KEY`（不配也能跑，所有 LLM 实验内置 mock）

### 三步跑起来

```bash
# 1. 安装依赖
cd labs
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt

# 2. 启动课程 Redis（M6 之后需要；M1-M5 不需要）
docker run -d --name course-redis -p 6399:6379 redis:7-alpine

# 3. 一键回归全部实验（自动验证 14 个实验的端到端行为）
python smoke_test.py
```

### 第一个实验

```bash
python -m uvicorn v0_hello_api.app:app --port 8801 --reload
curl http://127.0.0.1:8801/hello          # 你的第一个接口
curl -N http://127.0.0.1:8802/stream      # 亲眼看见"流式"（v2，另一个终端各起各的）
```

每个实验目录都有 README：启动命令、逐行代码讲解、自测题、常见坑。

## 实验地图

| 实验 | 主题 | 亮点 |
|---|---|---|
| A1 | asyncio 演示 | 串行 2s vs 并发 1s，眼见为实 |
| v0 | 第一个 FastAPI | 路由/Pydantic/OpenAPI |
| v2 | 分块流式 | `transfer-encoding: chunked` 实测 |
| v3a/b/c | SSE 三版本 | 手写裸格式 → `fastapi.sse` 原生 → sse-starlette；断线续传；POST+SSE |
| v4 | WebSocket 聊天室 | 双向帧 + ConnectionManager 广播 |
| v5 | LLM Token 流 | mock/真 API 零改动切换；浏览器打字机 |
| v6 | Agent 事件流 | 统一事件信封（对齐 AG-UI/Dify 命名） |
| **v7** | **毕业实验** | SSE 直播 + WS 遥控 + 人工审批（暂停/恢复/取消/批准） |
| r1 | 任务表 → Redis Hash | 适配层设计，跨连接可见 |
| r2 | 事件 → Redis Stream | 跨进程回放 + Last-Event-ID 续传 |
| **r3** | **多进程完全体** | Pub/Sub 双 Worker 协作，暂停/审批跨进程生效 |
| n1 | Nginx 事故对照 | `proxy_read_timeout 2s` 掐断 LLM 思考期长流（确定性复现） |
| **n2** | **终极拓扑** | Nginx → Worker×2 → Redis 全链路端到端 |
| v8 | 生产化设计 | Nginx/Docker/持久化配置与检查清单 |

v7 毕业实验的交互界面（`labs/v7_agent_server/index.html`）支持完整的
human-in-the-loop：启动任务 → 审批工具调用 → 暂停/恢复 → 断线刷新后自动续传。

## 交互式图表（9 张）

[`diagrams/`](diagrams/01-agent-server-architecture.html) 下 9 张 archify 生成的可交互 HTML（支持缩放、路径追踪、明暗主题）：

| # | 图 | 类型 |
|---|---|---|
| 01 | [全景架构](diagrams/01-agent-server-architecture.html) | architecture |
| 02 | [SSE 连接生命周期](diagrams/02-sse-lifecycle.html)（含断线续传） | sequence |
| 03 | [WebSocket 握手与广播](diagrams/03-websocket-handshake.html) | sequence |
| 04 | [Agent 事件管道](diagrams/04-agent-event-pipeline.html) | dataflow |
| 05 | [v7 双通道协作时序](diagrams/05-agent-server-dual-channel.html) | sequence |
| 06 | [v8 多 Worker 与 Redis](diagrams/06-multi-worker-redis.html) | architecture |
| 07 | [r3 数据面与控制面](diagrams/07-redis-data-plane.html) | dataflow |
| 08 | [流穿过 Nginx：read_timeout 生死判定](diagrams/08-nginx-sse-journey.html) | sequence |
| 09 | [终极总装：完整体系](diagrams/09-final-system.html) | architecture |

## 文档系统

- [`course/`](course/module-0-为什么需要网络通信.md) 7+1 份模块讲义（Markdown 源文件）
- [`lessons/`](lessons/0001-course-map.html) 3 节互动 HTML 课（含测验、SSE 格式实验室、事件时间线单步回放）
- [`reference/`](reference/sse-cheatsheet.html) SSE / WebSocket 速查表
- [`GLOSSARY.md`](GLOSSARY.md) 全课程统一术语表
- [`COURSE.md`](COURSE.md) **课程总纲（从这里开始学）**
- [`course/appendix-troubleshooting.md`](course/appendix-troubleshooting.html) 按症状索引的排障手册

所有 Markdown 文档由 [`tools/build_docs.py`](tools/build_docs.py) 渲染为统一风格的 HTML
（含左侧课程目录抽屉 + 上一篇/下一篇翻页条），改完 `.md` 后运行重建即可。

## 测试与质量保障

```bash
python labs/smoke_test.py                # 全量（约 3 分钟，14 个实验端到端）
python labs/smoke_test.py r3 n2          # 只跑指定实验
node tools/check_links.js                # 全站链接/导航自检（40+ HTML 页面）
python tools/build_docs.py               # 文档改动后重建 HTML
```

测试哲学：不 mock 网络，**在真实端口上测真实字节流**——SSE 分块时序、
断线续传位点、跨进程 seq 单调性、Pub/Sub 命令路由、Nginx 超时掐流，
全部有自动化断言。

## 目录结构

```
├── COURSE.md                 # 课程总纲（学习入口）
├── README.md                 # 本文件
├── GLOSSARY.md               # 术语表
├── MISSION.md / NOTES.md / RESOURCES.md
├── course/                   # 8 份模块讲义 + 排障附录（md 源文件）
├── labs/                     # 16 个可运行实验 + smoke_test.py
│   ├── a1_async/ … v0…v7/    #   基础 → 毕业实验
│   ├── r1…r3/                #   Redis 事件总线
│   ├── n1…n2/                #   Nginx 与部署
│   └── v8_production/        #   生产化配置
├── diagrams/                 # 9 张交互式架构图
├── lessons/ reference/       # 互动课 + 速查表
├── learning-records/         # 实测踩坑记录（ADR 风格）
└── tools/                    # build_docs.py / check_links.js
```

## 设计决策

- **协议优先复用成熟组件**：生产 SSE 用 `fastapi.sse` / `sse-starlette`，
  手写报文只出现在理解协议的教学实验里；事件命名对齐 [AG-UI](https://docs.ag-ui.com/concepts/events)
  与 [Dify](https://github.com/langgenius/dify)，学完即可读懂真实项目的通信层。
- **所有实验端口固定**（8801–8807、18901–18902），便于多终端跟练。
- **Redis/Nginx 均为官方 Docker 镜像**，Windows/macOS/Linux 行为一致；
  实验代码通过 `REDIS_URL` 环境变量适配任何 Redis 实例，连不上时自动降级
  fakeredis（单进程仿真）保证零门槛。
- Windows Git Bash 的 curl 中文编码坑、端口残留、孤儿进程等环境问题
  全部收录在排障附录，并已在自动化脚本中规避。

## 版本

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.10+（3.12 验证） | |
| FastAPI | ≥ 0.135（0.141 验证） | 原生 SSE（`fastapi.sse`） |
| Redis | 7-alpine（官方镜像） | 仅用 Hash/Stream/PubSub，4.0+ 兼容 |
| Nginx | 1.28-alpine（stable） | |

## License

MIT
