"""labs 全量冒烟测试：一键验证所有实验仍然可运行。

用法（labs/ 目录下）：
    python smoke_test.py            # 跑全部
    python smoke_test.py v0 v3b r3  # 只跑指定的

原理：v0-v7 的真实 app 用 uvicorn.Server 起在本机临时端口（独立线程），
用 httpx / websockets 做端到端断言。r 系/n 系（Redis/Nginx）依赖基础设施：
  - r1/r2/r3 需要 Redis：优先 course-redis 容器（自动 start），连不上则 SKIP
  - r2/r3/n1/n2 直接运行各自目录里的 verify_*.py（自带完整场景），按退出码判定
  - n1/n2 需要 Docker；不可用时 SKIP
学习记录 0002 的承诺在这里兑现：fastapi 升级后先跑本脚本，再改课程代码示例。
"""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import websockets
import uvicorn

# Windows 上 stdout 若是管道/重定向（Git Bash、CI、`> log.txt`），编码会退回系统 ANSI
# 代码页（简中 = GBK/cp936），此时 print("✔") 直接抛 UnicodeEncodeError 中断整个回归。
# 真实控制台下 Python 本来就写 UTF-8，这句等于无操作。所有可运行入口脚本都带这段守卫。
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

PASS: list[str] = []
SKIP: list[str] = []
FAIL: list[tuple[str, str]] = []


def start_server(app_module: str, port: int) -> uvicorn.Server:
    config = uvicorn.Config(f"{app_module}:app", host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    return server


def stop_server(server: uvicorn.Server) -> None:
    server.should_exit = True
    deadline = time.time() + 5
    while server.started and time.time() < deadline:
        time.sleep(0.05)


async def wait_ready(client: httpx.AsyncClient, url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if (await client.get(url)).status_code < 500:
                return
        except httpx.HTTPError:
            await asyncio.sleep(0.1)
    raise RuntimeError(f"server not ready: {url}")


def parse_sse_blocks(text: str) -> list[dict]:
    """把 SSE 字节流解析成 [{event, id, data}]——与 v5/index.html 同款解析器。"""
    events = []
    for block in text.split("\n\n"):
        ev: dict = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                ev["event"] = line[6:].strip()
            elif line.startswith("id:"):
                ev["id"] = line[3:].strip()
            elif line.startswith("data:"):
                ev.setdefault("data", "")
                ev["data"] += line[5:].strip()
        if ev:
            events.append(ev)
    return events


# ---------------- 各实验的检查 ----------------


async def check_v0(port: int) -> None:
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10) as c:
        r = await c.get("/hello", params={"name": "Agent"})
        assert r.json()["message"] == "hello, Agent", r.text
        r = await c.post("/chat", json={"text": "hello rag"})
        assert r.status_code == 200 and r.json()["echo"] == "hello rag", r.text
        r = await c.post("/chat", json={"tex": "typo"})
        assert r.status_code == 422, "Pydantic 校验应返回 422"
        r = await c.get("/tasks/abc")
        assert r.status_code == 422, "路径参数 int 类型校验应返回 422"


async def check_v2(port: int) -> None:
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=20) as c:
        async with c.stream("GET", "/stream") as r:
            stamps = []
            async for chunk in r.aiter_text():
                stamps.append(time.monotonic())
            assert len(stamps) >= 5, f"应分块到达，实际 {len(stamps)} 个 chunk"
            span = stamps[-1] - stamps[0]
            assert span > 2.0, f"chunk 之间应有时间间隔（流式），实际 {span:.2f}s"


async def check_v3a(port: int) -> None:
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=15) as c:
        async with c.stream("GET", "/events") as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
                if "event: done" in buf:
                    break
        for needle in (": heartbeat-comment", "retry: 3000", "event: count", "id: 1", "data: "):
            assert needle in buf, f"裸格式缺少 {needle!r}"
        assert "\n\n" in buf, "事件之间必须有分界空行"


async def check_v3b(port: int) -> None:
    base = f"http://127.0.0.1:{port}"
    async with httpx.AsyncClient(base_url=base, timeout=20) as c:
        # 1) 基础事件流
        async with c.stream("GET", "/events") as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
                if "event: done" in buf:
                    break
        evs = parse_sse_blocks(buf)
        assert evs and evs[0]["event"] == "tick" and evs[0]["id"] == "1", evs[:2]
        # 2) 断线续传：Last-Event-ID: 3 → 从 id 4 开始补发
        async with c.stream("GET", "/resumable", headers={"Last-Event-ID": "3"}) as r:
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
                if "event: done" in buf:
                    break
        first = parse_sse_blocks(buf)[0]
        assert first["id"] == "4", f"续传应从 id 4 开始，实际 {first}"
        # 3) POST + SSE 与裸 [DONE] 哨兵
        async with c.stream("POST", "/chat/stream", json={"text": "a b c"}) as r:
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
        assert "data: [DONE]" in buf, f"结束哨兵应为裸 [DONE]，实际 {buf[-120:]}"


async def check_v3c(port: int) -> None:
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=15) as c:
        async with c.stream("GET", "/events") as r:
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
                if "event: done" in buf:
                    break
    assert 'data: {"n": 1}' in buf, f"sse-starlette 应输出合法 JSON data 行，实际 {buf[:200]}"


async def check_v4(port: int) -> None:
    base = f"ws://127.0.0.1:{port}"
    async with websockets.connect(f"{base}/ws/echo") as ws:
        await ws.send("ping")
        assert await asyncio.wait_for(ws.recv(), 5) == "echo: ping"
    async with websockets.connect(f"{base}/ws/chat") as a, websockets.connect(
        f"{base}/ws/chat"
    ) as b:
        await asyncio.sleep(0.4)
        for _ in range(2):  # 排空系统消息
            try:
                await asyncio.wait_for(a.recv(), 0.4)
                await asyncio.wait_for(b.recv(), 0.4)
            except TimeoutError:
                break
        await a.send(json.dumps({"name": "A", "text": "大家好"}))
        got_b = json.loads(await asyncio.wait_for(b.recv(), 5))
        assert got_b["text"] == "大家好", got_b


async def check_v5(port: int) -> None:
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=30) as c:
        async with c.stream("POST", "/chat/stream", json={"text": "RAG"}) as r:
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
    evs = parse_sse_blocks(buf)
    types = [e.get("event") for e in evs]
    assert "token" in types and types[-1] == "done", types[-3:]
    assert evs[-1]["data"] == "[DONE]", evs[-1]


async def check_v6(port: int) -> None:
    base = f"http://127.0.0.1:{port}"
    async with httpx.AsyncClient(base_url=base, timeout=60) as c:
        async with c.stream("POST", "/agent/run", json={"question": "RAG"}) as r:
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
    evs = parse_sse_blocks(buf)
    types = [e.get("event") for e in evs]
    seqs = [int(e["id"]) for e in evs]
    assert types[0] == "agent_started" and types[-1] == "done", (types[:2], types[-2:])
    for needle in ("rag_search", "rag_result", "tool_call", "tool_result", "token"):
        assert needle in types, f"事件时间线缺少 {needle}"
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs), "seq 必须单调且唯一"
    # 重放：after=3 → 从 seq 4 开始；不存在任务 → 404
    task_id = json.loads(evs[0]["data"])["task_id"]
    async with httpx.AsyncClient(base_url=base, timeout=15) as c:
        async with c.stream("GET", f"/agent/tasks/{task_id}/replay", params={"after": 3}) as r:
            buf = ""
            async for chunk in r.aiter_text():
                buf += chunk
        first = parse_sse_blocks(buf)[0]
        assert first["id"] == "4", f"重放应从 seq 4 开始，实际 {first}"
        assert (await c.get("/agent/tasks/none/replay")).status_code == 404


async def check_v7(port: int) -> None:
    base = f"http://127.0.0.1:{port}"
    events: list[dict] = []
    finished = asyncio.Event()

    async with httpx.AsyncClient(base_url=base, timeout=60) as client:
        r = await client.post("/agent/tasks", json={"goal": "冒烟测试目标"})
        task_id = r.json()["task_id"]

        async def auto_approver() -> None:
            async with websockets.connect(f"ws://127.0.0.1:{port}/ws/control") as ws:
                while not finished.is_set():
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
                    except TimeoutError:
                        continue
                    if msg.get("type") == "approval_required" and msg.get("task_id") == task_id:
                        await ws.send(json.dumps({"task_id": task_id, "action": "approve"}))

        approver = asyncio.create_task(auto_approver())
        async with client.stream("GET", f"/agent/tasks/{task_id}/events") as resp:
            buf = ""
            async for chunk in resp.aiter_text():
                buf += chunk
                while "\n\n" in buf:
                    block, buf = buf.split("\n\n", 1)
                    ev = {}
                    for line in block.splitlines():
                        if line.startswith("event:"):
                            ev["event"] = line[6:].strip()
                        elif line.startswith("id:"):
                            ev["id"] = line[3:].strip()
                        elif line.startswith("data:"):
                            ev.setdefault("data", "")
                            ev["data"] += line[5:].strip()
                    if ev:
                        events.append(ev)
        finished.set()
        approver.cancel()

    types = [e.get("event") for e in events]
    assert types[0] == "agent_started" and types[-1] == "done", (types[:2], types[-2:])
    assert "tool_call" in types and "tool_result" in types, types
    seqs = [int(e["id"]) for e in events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs), "seq 必须单调且唯一"


async def check_r1(port: int) -> None:
    """r1：创建任务 → 并发消费 SSE（任务运行中）→ Hash 跨连接直查 → 终态复核。

    注意消费时序：r1 的事件在进程内存里，任务结束后 RUNNING 登记簿即清空
    （SSE 端点的 404 走 Depends）。所以要"边跑边读"。
    """
    import redis as redis_py

    base = f"http://127.0.0.1:{port}"
    direct = redis_py.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://127.0.0.1:6399/0"), decode_responses=True
    )
    async with httpx.AsyncClient(base_url=base, timeout=30) as c:
        tid = (await c.post("/agent/tasks", json={"goal": "smoke-r1"})).json()["task_id"]
        raw = direct.hget("agent:tasks", tid)
        assert raw and json.loads(raw)["goal"] == "smoke-r1", "Hash 中应能看到任务"

        done_hash = asyncio.Event()

        async def wait_terminal() -> None:
            while True:
                state = json.loads(direct.hget("agent:tasks", tid))["state"]
                if state in ("done", "error", "cancelled"):
                    done_hash.set()
                    return
                await asyncio.sleep(0.2)

        watcher = asyncio.create_task(wait_terminal())
        buf = ""
        async with c.stream("GET", f"/agent/tasks/{tid}/events") as r:
            async for chunk in r.aiter_text():
                buf += chunk
        await watcher
        assert "event: agent_started" in buf and "id: 1" in buf
        assert "event: done" in buf
        assert (await c.get(f"/agent/tasks/{tid}")).json()["state"] == "done"


LABS: dict[str, tuple[str, int, object]] = {
    "v0": ("v0_hello_api.app", 18801, check_v0),
    "v2": ("v2_streaming.app", 18802, check_v2),
    "v3a": ("v3_sse.v3a_raw_sse", 18803, check_v3a),
    "v3b": ("v3_sse.v3b_fastapi_sse", 18813, check_v3b),
    "v3c": ("v3_sse.v3c_sse_starlette", 18823, check_v3c),
    "v4": ("v4_websocket.app", 18804, check_v4),
    "v5": ("v5_llm_stream.app", 18805, check_v5),
    "v6": ("v6_agent_events.app", 18806, check_v6),
    "v7": ("v7_agent_server.app", 18807, check_v7),
    "r1": ("r1_redis_tasks.app", 18901, check_r1),
    # r2/r3/n1/n2：check 字段为各自的完整验证脚本（相对 labs/，自带服务器与场景）
    "r2": (None, 0, "r2_redis_stream/verify_replay.py"),
    "r3": (None, 0, "r3_redis_fanout/verify_multiworker.py"),
    "n1": (None, 0, "n1_nginx_proxy/verify_through_nginx.py"),
    "n2": (None, 0, "n2_full_stack/verify_topology.py"),
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6399/0")


def docker_ready() -> bool:
    try:
        r = subprocess.run(["docker", "ps"], capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def ensure_redis() -> bool:
    """确保 Redis 可达：优先启动已存在的 course-redis 容器；没有则尝试 docker run。"""
    import redis as redis_py

    try:
        redis_py.Redis.from_url(REDIS_URL, socket_connect_timeout=0.5).ping()
        return True
    except Exception:
        pass
    if not docker_ready():
        return False
    sh(["docker", "start", "course-redis"])
    time.sleep(2)
    try:
        redis_py.Redis.from_url(REDIS_URL, socket_connect_timeout=1).ping()
        return True
    except Exception:
        sh(["docker", "run", "-d", "--name", "course-redis", "-p", "6399:6379", "redis:7-alpine"])
        time.sleep(2)
        try:
            redis_py.Redis.from_url(REDIS_URL, socket_connect_timeout=1).ping()
            return True
        except Exception:
            return False


def run_script(rel: str, timeout: int = 240) -> None:
    # 子进程必须显式拿 UTF-8：它的 stdout 也是管道，否则 print("✔") 会在子进程里崩掉
    # （历史上正是这里吞掉了 r2/r3/n1/n2：子进程 rc=1 或解码失败 → stdout=None → TypeError）
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, rel], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env,
                       timeout=timeout, cwd=".")
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    tail = out.splitlines()[-4:]
    for line in tail:
        print(f"    {line}")
    if r.returncode != 0:
        raise RuntimeError(f"验证脚本退出码 {r.returncode}")


async def run_one(name: str) -> None:
    if name in ("r1", "r2", "r3"):
        if not ensure_redis():
            SKIP.append(name)
            print(f"  ⏭ {name}（Redis 不可达：docker run -d --name course-redis -p 6399:6379 redis:7-alpine）")
            return
    if name in ("n1", "n2"):
        if not docker_ready():
            SKIP.append(name)
            print(f"  ⏭ {name}（Docker 不可用）")
            return
        if name == "n2" and not ensure_redis():
            SKIP.append(name)
            print("  ⏭ n2（Redis 不可达）")
            return

    module, port, check = LABS[name]
    if callable(check):
        server = start_server(module, port)
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await wait_ready(c, f"http://127.0.0.1:{port}/")
            await asyncio.wait_for(check(port), timeout=120)
            PASS.append(name)
            print(f"  ✔ {name}")
        except Exception as exc:  # noqa: BLE001 —— 汇总所有失败继续跑
            FAIL.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  ✘ {name} → {type(exc).__name__}: {exc}")
        finally:
            stop_server(server)
            await asyncio.sleep(0.2)
    else:
        # r2/r3/n1/n2：自带验证脚本（自起服务器、自含完整场景），按退出码判定
        try:
            run_script(check)
            PASS.append(name)
            print(f"  ✔ {name}")
        except Exception as exc:  # noqa: BLE001
            FAIL.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  ✘ {name} → {type(exc).__name__}: {exc}")


async def main(targets: list[str]) -> None:
    print(f"labs 冒烟测试：{', '.join(targets)}\n")
    t0 = time.monotonic()
    for name in targets:
        await run_one(name)
    print(f"\n结果：{len(PASS)} 通过 / {len(FAIL)} 失败 / {len(SKIP)} 跳过，用时 {time.monotonic() - t0:.1f}s")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:] or list(LABS)
    unknown = [a for a in args if a not in LABS]
    if unknown:
        print(f"未知实验：{unknown}（可选：{', '.join(LABS)}）")
        sys.exit(2)
    asyncio.run(main(args))
