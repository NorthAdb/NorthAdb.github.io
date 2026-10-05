"""r2 跨进程回放验证（自动化）：这是 v7 在多进程下做不到的事。

流程：
  1. 起服务进程 A（18902）
  2. 在 A 上创建任务并等它跑完
  3. 起服务进程 B（18903）——全新的进程，RUNNING 里什么都没有
  4. 向 B 请求完整事件流（不带 Last-Event-ID）→ 应当收到全部历史
  5. 向 B 带 Last-Event-ID: 3 再请求 → 应当从 seq 4 开始补发
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

# Windows 管道/重定向下 stdout 退回 GBK：print("✔") 会抛 UnicodeEncodeError 中断脚本
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

LABS = Path(__file__).resolve().parent.parent  # labs/
sys.path.insert(0, str(LABS))
from redis_client import get_redis  # noqa: E402

R = get_redis()


def parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.split("\n\n"):
        ev = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                ev["event"] = line[6:].strip()
            elif line.startswith("id:"):
                ev["id"] = int(line[3:].strip())
            elif line.startswith("data:"):
                ev.setdefault("data", "")
                ev["data"] += line[5:].strip()
        if ev:
            events.append(ev)
    return events


async def serve(port: int) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uvicorn", "r2_redis_stream.app:app",
        "--port", str(port), "--log-level", "error",
        cwd=LABS,
    )


async def wait_ready(client: httpx.AsyncClient, url: str) -> None:
    import time

    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            if (await client.get(url)).status_code < 500:
                return
        except httpx.HTTPError:
            await asyncio.sleep(0.2)
    raise RuntimeError(f"not ready: {url}")


async def main() -> None:
    procs = []
    try:
        procs.append(await serve(18902))
        procs.append(await serve(18903))
        async with httpx.AsyncClient(timeout=30) as c:
            await wait_ready(c, "http://127.0.0.1:18902/agent/tasks")
            await wait_ready(c, "http://127.0.0.1:18903/agent/tasks")

            # 进程 A：创建任务并等它跑完
            tid = (await c.post("http://127.0.0.1:18902/agent/tasks",
                                json={"goal": "跨进程回放验证"})).json()["task_id"]
            while True:
                state = (await c.get(f"http://127.0.0.1:18902/agent/tasks/{tid}")).json()["state"]
                if state in ("done", "error", "cancelled"):
                    break
                await asyncio.sleep(0.3)
            print(f"[A] 任务 {tid} 已完成（state={state}）")

            # 进程 B：全新进程，回放完整事件流
            async with c.stream("GET", f"http://127.0.0.1:18903/agent/tasks/{tid}/events") as r:
                buf = ""
                async for chunk in r.aiter_text():
                    buf += chunk
            evs = parse_sse(buf)
            types = [e["event"] for e in evs]
            assert types[0] == "agent_started" and types[-1] == "done", types
            print(f"[B] 跨进程回放 ✔ {len(evs)} 条事件（{types[0]} … {types[-1]}）")

            # 续传：Last-Event-ID: 3 → 从 seq 4 开始
            async with c.stream("GET", f"http://127.0.0.1:18903/agent/tasks/{tid}/events",
                                headers={"Last-Event-ID": "3"}) as r:
                buf = ""
                async for chunk in r.aiter_text():
                    buf += chunk
            first = parse_sse(buf)[0]
            assert first["id"] == 4, first
            print(f"[B] 断线续传 ✔ 从 seq 4 开始补发（Last-Event-ID: 3）")
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            await p.wait()
    _ = json, R


if __name__ == "__main__":
    asyncio.run(main())
