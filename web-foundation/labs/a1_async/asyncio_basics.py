"""实验 A1：Python 异步编程——SSE/WebSocket/LLM Streaming 共同的地基。

运行：python asyncio_basics.py
看什么：四个小实验的输出顺序和时间，验证"并发"到底发生了什么。
"""

import asyncio
import time


# ---------- 实验 1：同步阻塞 vs 异步并发 ----------
# 关键直觉：async 函数只有在 await 时才会"让出"执行权。
# 如果把 await 换成 time.sleep（同步阻塞），整个事件循环都会被卡住。


async def fetch(name: str, seconds: float) -> str:
    print(f"  [{name}] 开始请求... t={time.monotonic() - T0:.1f}s")
    await asyncio.sleep(seconds)  # 模拟网络 IO：发起请求后不占着 CPU
    print(f"  [{name}] 得到响应    t={time.monotonic() - T0:.1f}s")
    return f"{name} 的结果"


T0 = time.monotonic()


async def demo_sync_vs_async() -> None:
    print("\n=== 1. 同步阻塞（串行，总耗时 = 1 + 1 = 2 秒）===")

    async def blocking(name: str) -> str:
        print(f"  [{name}] 开始 t={time.monotonic() - T0:.1f}s")
        time.sleep(1)  # 同步 sleep：占着事件循环不放，别人干不了活
        print(f"  [{name}] 结束 t={time.monotonic() - T0:.1f}s")
        return name

    await blocking("A")
    await blocking("B")

    print("\n=== 2. 异步并发（gather，总耗时 ≈ 1 秒）===")
    results = await asyncio.gather(
        fetch("A", 1.0),
        fetch("B", 1.0),
        fetch("C", 1.0),
    )
    print(f"  gather 返回: {results}")


# ---------- 实验 2：create_task——"后台任务" ----------
# SSE/Agent 场景：用户请求立即返回，任务在后台慢慢跑。
# v7 毕业实验里的 AgentTask 就是这样启动的。


async def demo_create_task() -> None:
    print("\n=== 3. create_task：请求先返回，任务后台跑 ===")

    async def long_job() -> None:
        await asyncio.sleep(1.5)
        print("  [后台任务] 我跑完了 t={:.1f}s".format(time.monotonic() - T0))

    task = asyncio.create_task(long_job())  # 提交后台，立刻返回
    print(f"  主流程没等它，直接继续 t={time.monotonic() - T0:.1f}s")
    await asyncio.sleep(0.2)
    print(f"  主流程做点别的事 t={time.monotonic() - T0:.1f}s")
    await task  # 真正需要结果时才等它（这里只是为了不让程序提前退出）


# ---------- 实验 3：Queue——生产者/消费者模型 ----------
# 这是 SSE、WebSocket、Agent 事件流的通用骨架：
#   Agent（生产者）把事件放进队列，SSE 连接（消费者）从队列取出来发给浏览器。


async def demo_queue() -> None:
    print("\n=== 4. Queue：生产者/消费者（Agent 事件流的雏形）===")

    queue: asyncio.Queue[str] = asyncio.Queue()

    async def producer() -> None:
        for i in range(1, 6):
            await queue.put(f"事件-{i}")
            print(f"  [生产者] 放入 事件-{i}")
            await asyncio.sleep(0.3)
        await queue.put(None)  # 哨兵：告诉消费者"没有更多了"

    async def consumer() -> None:
        while True:
            item = await queue.get()
            if item is None:
                print("  [消费者] 收到哨兵，退出")
                break
            print(f"  [消费者] 取出 {item}")

    await asyncio.gather(producer(), consumer())


if __name__ == "__main__":
    asyncio.run(demo_sync_vs_async())
    asyncio.run(demo_create_task())
    asyncio.run(demo_queue())
    print("\n全部演示完成。回到课程文档，回答自测问题。")
