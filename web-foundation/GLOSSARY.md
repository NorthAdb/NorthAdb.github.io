# GLOSSARY：网络通信 × Agent Server 术语表

> 课程统一用词。写代码、读开源项目、提问时按此表对齐。

| 术语 | 英文 | 一句话定义 | 详见 |
|---|---|---|---|
| 事件循环 | event loop | 异步调度器：谁在 await 就把 CPU 给谁 | M1 L1.1 |
| 协程 | coroutine | 可暂停/继续的函数（async def） | M1 L1.1 |
| Task | task | 提交给事件循环后台并发运行的协程 | M1 L1.1, M4 L4.4 |
| 生产者/消费者 | producer/consumer | 通过队列解耦的两侧：Agent 生产事件，连接消费事件 | M1 L1.1, M4 L4.4 |
| 长连接 | keep-alive | 一条 TCP 连接服务多次请求/持续传输 | M1 L1.3 |
| 分块传输 | chunked transfer encoding | 响应体切成块陆续发送，无 content-length | M2 L2.2 |
| 流式 | streaming | 边生成边发送，不等全部完成 | M2 L2.2 |
| 服务器推送事件 | SSE / Server-Sent Events | 基于 HTTP 的服务器→客户端单向事件流协议 | M2 L2.3–L2.5 |
| 事件流 | event stream | SSE 响应体：若干"字段行+空行"构成的事件序列 | M2 L2.3 |
| 心跳 | heartbeat / ping | 空闲期发送的保活数据（SSE 注释行 / WS ping 帧） | M2 L2.4, M5 L5.2 |
| 断线续传 | resume | 重连时凭 Last-Event-ID 从断点补发事件 | M2 L2.4, M4 L4.4 |
| 单调序号 | seq / id | 事件日志位点：SSE id、重放依据、排序键三合一 | M4 L4.2 |
| 协议升级 | HTTP Upgrade | WebSocket 借 HTTP 入口换协议的握手（101） | M3 L3.1 |
| 帧 | frame | WebSocket 连接上的最小传输单元 | M3 L3.1 |
| 探活 | ping/pong | WS 协议层心跳，一端 ping 另一端必须 pong | M3 L3.1 |
| 关闭码 | close code | 1000 正常、1001 对端离开、1011 服务器错误…… | M3 L3.1 |
| 连接管理器 | ConnectionManager | 服务端活跃连接的登记簿：登记/单发/广播 | M3 L3.3 |
| 广播 | broadcast | 一条消息发给所有活跃连接 | M3 L3.3 |
| 令牌流 | token streaming | LLM 逐 token 输出并实时下发 | M4 L4.1 |
| 打字机效果 | typewriter effect | 前端把 token 流拼接渲染的效果 | M4 L4.1 |
| 事件信封 | event envelope | 统一事件结构 {seq, type, task_id, timestamp, data} | M4 L4.2 |
| 三段式事件 | start/content/end triad | 有开始有结束的事件配对（tool_call/tool_result） | M4 L4.2 |
| 事件总线 | event bus | Agent 事件向多个出口分发的枢纽 | M4 L4.4 |
| 人在回路 | human-in-the-loop | 运行中等待人类审批/输入（v7 的 approval Future） | M4 L4.4 |
| 反向代理 | reverse proxy | Nginx 等前置网关；流式的坑主要在缓冲与超时 | M5 L5.2 |
| 发布/订阅 | Pub/Sub | Redis 的多进程广播原语，替代进程内广播 | M5 L5.2 |
| 首字延迟 | TTFT | 从发问到第一个 token 到达的延迟，流式体验核心指标 | M5 L5.2 |
| 哈希表 | Hash | Redis 二级字典：任务表外移的落点（HSET/HGET/HVALS） | M6 L6.2 |
| 流 | Stream | Redis 持久日志：XADD 写入、XRANGE 区间读，天然支持按位点续传 | M6 L6.3 |
| 发布订阅 | Pub/Sub | Redis 即发即弃广播：实时性担当，但不留存消息 | M6 L6.4 |
| 控制平面 | control plane | 命令如何路由到属主进程的通道（control 频道） | M6 L6.4 |
| 命令监听 | control listener | 属主进程内订阅控制频道、执行闸门操作的协程 | M6 L6.4 |
| 事件桥 | event bridge | 进程内唯一订阅协程：Pub/Sub → 本地队列的分发器 | M6 L6.4 |
| 反向代理 | reverse proxy | Nginx 等前置网关；流式的坑主要在缓冲与超时 | M5/M7 |
| 上游 | upstream | Nginx 的后端服务器组（负载均衡目标） | M7 L7.3 |
| 代理缓冲 | proxy_buffering | Nginx 攒上游数据再转发的开关，SSE 必须关 | M5/M7 |
| 代理读超时 | proxy_read_timeout | 上游静默超过阈值即掐断连接——事故最高频来源 | M7 L7.2 |
| 豁免头 | X-Accel-Buffering: no | 后端发给 Nginx 的"别缓冲我"信号 | M7 L7.2 |
