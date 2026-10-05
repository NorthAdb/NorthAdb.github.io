# r2 · 事件日志外移到 Redis Stream

目标：解决 v7/r1 的第二个局限——事件历史只在本进程内存里。
外移后，**任何进程**都能回放任何任务的完整事件流，Last-Event-ID 续传跨进程成立。

## 版本说明

Redis Stream 从 4.0 起可用，7.x/8.x 行为一致。本实验在 Docker 官方
`redis:7-alpine` 上开发验证；生产同版本栈无缝迁移。

## 一键验证（自动起两个真实进程）

```bash
python r2_redis_stream/verify_replay.py
```

流程：A 进程创建任务并跑完 → B 进程（全新，内存为空）回放完整事件流 →
再带 `Last-Event-ID: 3` 验证从 seq 4 补发。输出：

```
[A] 任务 xxx 已完成（state=done）
[B] 跨进程回放 ✔ 26 条事件（agent_started … done）
[B] 断线续传 ✔ 从 seq 4 开始补发（Last-Event-ID: 3）
```

## 代码流程讲解

1. **seq = INCR**（agent.py emit）：跨进程原子的单调计数器。v6/v7 的 `len(buffer)`
   只在本进程有意义——分布式环境下序号必须来自共享存储。
2. **XADD 字段设计**：`seq / type / ts / data(JSON)`。业务 seq 与 Stream 条目 ID
   （时间戳形态）是不同轴：续传位点用业务 seq，全量遍历用 XRANGE。
3. **SSE 端点三段式升级**（app.py）：XRANGE 回放（任何进程）→ 本进程实时跟随（若有）
   → 终态关流。404 语义在 `Depends` 依赖里（存在 Stream 或任务在本进程运行即放行）。

## 自测问题

1. 为什么不能直接用 Stream 条目 ID 当 Last-Event-ID？（提示：两个 Worker 各自 XADD，
   条目 ID 按时间交错，任务内序号会乱）
2. 事件量大了以后 XRANGE 全量+过滤的瓶颈在哪？怎么改造成增量读？
3. Stream 要设 `MAXLEN ~ 100000` 防止无限增长——截断后旧任务的续传会怎样？
   （答案：超过保留窗口的历史不可续传——生产用"Stream + PostgreSQL 双写"解决）

## 延伸

- r3 会把"实时跟随"也从进程内队列换成 Pub/Sub，实现真正的任意 Worker 全功能。
