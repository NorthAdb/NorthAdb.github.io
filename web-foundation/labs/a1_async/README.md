# A1 asyncio 基础演示

目标：不开服务器，用四个纯终端小实验建立异步直觉——这是 SSE/WebSocket/Agent 任务的地基。

## 运行

```bash
python a1_async/asyncio_basics.py
```

## 四个演示分别看什么

1. **串行阻塞**（约 2 秒）：`time.sleep` 占着事件循环不放——两个任务只能排队。对照第 2 个演示理解"假并发"。
2. **gather 并发**（约 1 秒）：三个 1 秒任务同时跑。每个 `await asyncio.sleep` 挂起的瞬间，事件循环去推进别人。
3. **create_task**：主流程不等后台任务继续往下走——v7 毕业实验的 AgentTask 就是这样启动的。
4. **Queue 生产者/消费者**：把"生产者"读成 Agent、"消费者"读成 SSE 连接，就是模块 4 的全部架构。

## 自测问题

1. `async def` 里混用 `time.sleep` 会发生什么？怎么修？
2. `gather` 和顺序 `await` 的时间差从哪来？
3. `create_task` 返回值如果不保存，会有什么风险？（提示：任务可能被垃圾回收 / 异常无人接收）
4. Queue 的 `None` 哨兵起什么作用？换成 `queue.task_done()` + `join()` 行不行？

## 延伸

- [asyncio 官方文档](https://docs.python.org/zh-cn/3/library/asyncio.html)——本实验之后只需精读 Coroutines 与 Tasks 两节。
