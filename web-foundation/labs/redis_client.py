"""labs 共享的 Redis 连接工厂（r1/r2/r3 使用）。

连接策略（适配器模式——"面向接口，不面向具体实现"）：
1. 优先读环境变量 REDIS_URL（默认 redis://127.0.0.1:6399/0，本课程配套的本地 redis-server）
2. 连不上 → 降级到 fakeredis（纯 Python 的 Redis 仿真，接口与 redis-py 完全一致），
   保证"没有 Redis 也能把课听完"；但 fakeredis 只在单进程内有效，
   跨 Worker 实验（r3 的多进程验证）必须用真 Redis。

生产代码不要这样写——生产应明确依赖真实 Redis 并处理好连接池/重连；
这里的降级是为了让实验环境零门槛。
"""

import os

import redis


def get_redis() -> redis.Redis:
    """同步客户端（r1/r2 用：命令快、无长等待，够用）。"""
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6399/0")
    try:
        r = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.5)
        r.ping()
        return r
    except Exception:
        import fakeredis

        # FakeServer：同一进程内的多个连接共享同一块内存（模拟"多个客户端连同一 Redis"）
        server = fakeredis.FakeServer()
        return fakeredis.FakeRedis(server=server, decode_responses=True)


def get_async_redis():
    """异步客户端（r3 起用：异步服务里做 Pub/Sub 长监听必须用它）。

    为什么 r3 不能继续用同步客户端：Pub/Sub 的 get_message 会长时间挂起等待，
    在事件循环里直接调同步版会卡住整个服务——这正是模块 1"阻塞事件循环"的翻版。
    """
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6399/0")
    try:
        # 连通性探测在同步阶段做（模块导入时不能 await）
        probe = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.5)
        probe.ping()
        probe.close()
        import redis.asyncio as aioredis

        return aioredis.Redis.from_url(url, decode_responses=True)
    except Exception:
        import fakeredis

        server = fakeredis.FakeServer()
        return fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
