"""跨连接验证：用一条全新的 Redis 连接读取任务表——模拟"另一个进程"在看。

先启动服务并发起一个任务，再运行本脚本：
  python r1_redis_tasks/verify_cross_connection.py
"""

import json
import os
import sys

import redis

# Windows 管道/重定向下 stdout 退回 GBK：print("✔") 会抛 UnicodeEncodeError 中断脚本
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

r = redis.Redis.from_url(
    os.environ.get("REDIS_URL", "redis://127.0.0.1:6399/0"), decode_responses=True
)
assert r.ping(), "Redis 未连接"

tasks = [json.loads(v) for v in r.hvals("agent:tasks")]
print(f"另一条连接读到 {len(tasks)} 个任务：")
for t in tasks:
    print(f"  {t['task_id']}  [{t['state']:<9}]  {t['goal']}")

if tasks:
    print("\n✔ Hash 里的数据对所有连接可见——这就是'外移'的含义。")
    print("  对照：这些任务的事件流此刻仍在本进程内存里（r2 解决）。")
