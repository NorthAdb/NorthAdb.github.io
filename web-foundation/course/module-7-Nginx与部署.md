# 模块 7：生产基础设施 II —— Nginx 与部署

> 3 课 · 实验 n1/n2 · 目标：让流式服务活着穿过反向代理，并把前面所有模块组装成完整拓扑
>
> 配图：Nginx 事故路径 [diagrams/08-nginx-sse-journey.html](../diagrams/08-nginx-sse-journey.html) · 终极总装 [diagrams/09-final-system.html](../diagrams/09-final-system.html)

---

## L7.1 反向代理：流式服务的第一道门

### 目标
说清反向代理在链路里的位置与价值；掌握流式相关的三组配置。

### 概念

正向代理替"客户端"出门办事；**反向代理**替"服务器"接待——浏览器以为自己在跟后端说话，
其实对面是 Nginx。它带来：统一入口与 TLS 终结、负载均衡、静态资源分流、限流防护。
代价是：**流必须在它那里"活下来"**——三组配置决定生死：

1. **proxy_buffering**（缓冲）：on 时 Nginx 尽量从上游读进缓冲区再转发；
   下游快于上游时影响不大，但叠加 gzip/TLS/慢客户端后，SSE 小事件会被攒住。
   正确配置：`proxy_buffering off;`（或依赖后端自动发送的 `X-Accel-Buffering: no` 响应头——
   fastapi.sse 已经在发；旧配置若 `proxy_hide_header` 掉它，豁免即失效）。
2. **proxy_read_timeout**（读超时）：**上游静默**超过阈值即掐断连接（默认 60s）。
   LLM 思考 60 秒不吐 token = 连接死亡。解法两层：阈值调大 + 心跳重置定时器。
3. **WebSocket Upgrade 透传**：握手头 `Upgrade`/`Connection` 必须原样送达，
   标准写法是 `map $http_upgrade $connection_upgrade` + `proxy_set_header`。

### 实操
n1 实验自动完成这一切；先跑一遍看现象，再逐行读两份配置文件：
```bash
python -m uvicorn n1_nginx_proxy.app:app --host 0.0.0.0 --port 8807
python n1_nginx_proxy/verify_through_nginx.py
```
> 为什么 `--host 0.0.0.0`：Nginx 容器经 `host.docker.internal` 回访宿主机；
> uvicorn 默认只绑 127.0.0.1 会拒绝来自虚拟网卡的连接（502 现场之一）。

---

## L7.2 n1：一次事故的完整解剖

### 目标
亲手复现"read_timeout 掐流"事故并修复；理解为什么心跳能救命。

### 实操与现象

`verify_through_nginx.py` 做两次部署、同一后端、同一 URL：

1. **正确配置**（n1-good.conf：buffering off + read_timeout 3600s）：
   10 个事件陆续到达（跨度 ≈ 7s），WebSocket Upgrade 透传正常。
2. **事故配置**（n1-incident.conf：read_timeout 2s）：
   后端发 3 个事件后"思考"静默 4 秒 → Nginx 在静默窗口把连接掐断，
   客户端收到残缺流或连接重置。

### 事故的确定性来源（重要实验结论）

静默窗口（4s）> 阈值（2s）时事故**必然发生**；而"每 0.5s 一个小事件"的流
在快链路上即使 buffering on 也不会卡（下游快于上游，缓冲攒不起来）。
真实世界的"卡顿"通常是 buffering + gzip + TLS + 慢客户端叠加的结果——
所以正确姿势是**显式**关闭缓冲、显式排除 SSE 的 gzip 压缩，而不是赌运行时行为。

### 心跳为什么救命

fastapi.sse 内置 15 秒一条 `: ping` 注释行。对客户端：注释行被忽略，零打扰；
对 Nginx：每收到字节，read_timeout 定时器重置。一条注释同时安抚了
"读超时"与"中间设备空闲断连"两个杀手——这是 M2 L2.4 埋的伏笔的完全体。

### 自测
1. "上游慢"和"上游静默"哪个会触发 read_timeout？分别对应什么场景？
2. `X-Accel-Buffering: no` 是谁发的、给谁看的？运维不认识它会发生什么？
3. 为什么 gzip 压缩对 SSE 危险？（提示：压缩需要攒数据；浏览器会主动带 Accept-Encoding）

---

## L7.3 n2：完整体系总装

### 目标
跑通"浏览器 → Nginx → Worker×2 → Redis"全链路；确认 r1/r2/r3 的每一层外移都在拓扑里各就各位。

### 实操
```bash
python n2_full_stack/verify_topology.py
```
脚本自动起两个 Worker 进程 + Nginx 容器（upstream 指向
`host.docker.internal:18901/18902`），然后断言四件事：
1. 6 个任务经 Nginx 创建（负载均衡打散），两个 Worker 都能看到全部任务（Hash）
2. SSE 经 Nginx 落在任意 Worker，都能看到完整事件流（Stream 回放 + Pub/Sub 实时）
3. WS 审批经 Nginx 路由到属主进程生效（人工审批闭环）
4. 终态写入 Hash，经 Nginx 查询 state=done

### 配置讲解（conf/n2-full.conf）
- `upstream backend { server host.docker.internal:18901; ... }`：默认轮询负载均衡。
- `map $http_upgrade $connection_upgrade`：WS 升级头的标准写法（map 必须在 http 层）。
- SSE location：`proxy_buffering off` + `proxy_read_timeout 3600s`——n1 的全部教训浓缩成两行。

### 生产检查清单（对照 09 总装图逐项确认）

- [ ] Nginx：buffering off、read_timeout 调大、WS Upgrade 透传、TLS 终结
- [ ] Worker：`--workers N` 或多实例 + Redis 数据面/控制面（r3）
- [ ] Redis：Hash 任务表 / Stream 事件日志（设 MAXLEN）/ Pub/Sub 广播
- [ ] 持久化：任务与事件落 PostgreSQL（Redis Stream 设上限后历史进库）
- [ ] 认证：WS 连接校验 token；SSE 校验任务归属
- [ ] 可观测：连接数、事件吞吐、TTFT（首字延迟）、P95
- [ ] 优雅停机：SIGTERM 后完成/取消运行中任务再退出

### 自测
1. 为什么"创建与订阅落在不同 Worker"在 n2 里不再是问题？靠的是哪三步外移？
2. 负载均衡轮询意味着同一用户的 SSE 和 WS 可能落在不同 Worker——控制命令为什么还能生效？
3. 如果某个 Worker 崩溃，它属主的任务会卡在 running——设计一个"心跳+超时接管"方案。

---

## 课程终点

到这里，最初的那张全景图（diagrams/01）里的每一个方框、每一条线，你都亲手实现过。
毕业标准见 COURSE.md 第 7 节；下一步的世界是 MCP 服务端、AG-UI 接入与多 Agent 编排——
但那是新课程了。
