# n2 · 终极拓扑：Nginx → Worker×2 → Redis

目标：把 r3 的多进程 Agent Server 和 n1 的 Nginx 组装成**完整生产拓扑**，
并用一条命令验证"浏览器 → Nginx → 两个 Worker → Redis"全链路协作。

## 前置

```bash
docker run -d --name course-redis -p 6399:6379 redis:7-alpine   # 若尚未启动（r1）
```

## 一键验证

```bash
python n2_full_stack/verify_topology.py
```

它自动：清理端口残留 → 起两个 Worker 进程（18901/18902）→ 起 Nginx 容器（8080，
upstream 指向 `host.docker.internal:18901/18902`）→ 然后断言四件事：

1. 6 个任务经 Nginx 创建，负载均衡打散，**两个 Worker 都能看到全部任务**（Hash）
2. SSE 订阅经 Nginx 落在任意 Worker，都能看到完整事件流（Stream 回放 + Pub/Sub 实时）
3. WS 审批命令经 Nginx 路由到属主进程生效（人工审批闭环）
4. 终态写入 Hash，经 Nginx 查询 state=done

## 配置讲解（conf/n2-full.conf）

- `upstream backend { server host.docker.internal:18901; ... }`：Nginx 默认轮询负载均衡；
  容器里访问宿主机用 host.docker.internal（Docker Desktop 提供；Linux 用 172.17.0.1）。
- `map $http_upgrade $connection_upgrade`：WebSocket 升级头的标准写法（map 必须在 http 层）。
- SSE location：buffering off + read_timeout 3600s（n1 的全部教训浓缩在这两行）。

## 自测问题

1. 为什么"创建任务的请求"和"订阅事件的请求"落在不同 Worker 也完全没问题？
   这依赖 r1/r2/r3 的哪三个外移？
2. 如果运维把 nginx.conf 里的 `proxy_buffering off` 删了，用户体验会发生什么变化？
   什么条件下不会复现？（提示：看 n1 的对照实验结论）
3. 负载均衡轮询意味着同一个用户的 SSE 和 WS 可能落在不同 Worker——控制命令怎么还能生效？
   （提示：control 频道的"路由"语义）

## 延伸

- 生产再加三样：认证（Nginx 层 JWT 校验或应用层）、事件持久化（PostgreSQL）、
  可观测性（连接数/事件吞吐/TTFT 指标）。这超出本课程范围，但架构位置你已经全部知道。
