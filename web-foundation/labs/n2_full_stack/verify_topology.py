"""n2 终极拓扑验证：完整体系端到端（全部经由 Nginx:8080）。

  浏览器(curl/httpx/websockets) → Nginx(8080) → Worker×2(18901/18902) → Redis(6399)

证明四件事：
  1. 创建 6 个任务（负载均衡打散到两个 Worker），每个 Worker 都能全部列出（Hash）
  2. SSE 订阅经 Nginx 落在任意 Worker，都能看到完整事件流（Stream+Pub/Sub）
  3. WS 控制命令经 Nginx 路由到属主进程生效（审批 human-in-the-loop）
  4. 全流程直到 done，终态写入 Hash（经 Nginx 查询）

运行：python n2_full_stack/verify_topology.py   （需要 Docker + course-redis 容器）
"""

import asyncio
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import websockets

# Windows 管道/重定向下 stdout 退回 GBK：print("✔") 会抛 UnicodeEncodeError 中断脚本
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

LABS = Path(__file__).resolve().parent.parent
NGINX_PORT = 8080


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


def sh(cmd: list[str]) -> None:
    subprocess.run(cmd, capture_output=True)


def docker_running(name: str) -> bool:
    """容器是否真的在跑——`docker run` 端口被占时不会报错到我们这儿。"""
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0 and r.stdout.strip() == "true"


def start_nginx() -> None:
    sh(["docker", "rm", "-f", "course-nginx-n2"])
    conf_path = str((LABS / "n2_full_stack" / "conf" / "n2-full.conf").resolve()).replace("\\", "/")
    sh(["docker", "run", "-d", "--name", "course-nginx-n2", "-p", f"{NGINX_PORT}:8080",
        "-v", f"{conf_path}:/etc/nginx/conf.d/default.conf", "nginx:1.28-alpine"])
    if not docker_running("course-nginx-n2"):
        raise RuntimeError(
            f"nginx 容器没起来：宿主 {NGINX_PORT} 很可能已被别的容器占用"
            f"（docker ps --format '{{{{.Names}}}} {{{{.Ports}}}}' 查看后 docker rm -f <名字>）"
        )


async def serve(port: int) -> asyncio.subprocess.Process:
    log = open(Path(tempfile.gettempdir()) / f"n2_server_{port}.log", "wb")
    return await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uvicorn", "r3_redis_fanout.app:app",
        "--host", "0.0.0.0", "--port", str(port), "--log-level", "error",
        cwd=LABS, stdout=log, stderr=log,
    )


def kill_port(port: int) -> None:
    out = subprocess.run(["netstat", "-ano"], capture_output=True).stdout.decode(
        "utf-8", errors="ignore"
    )
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            sh(["taskkill", "/PID", line.split()[-1], "/F"])


async def wait_ready(client: httpx.AsyncClient, url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if (await client.get(url)).status_code < 500:
                return
        except httpx.HTTPError:
            await asyncio.sleep(0.2)
    raise RuntimeError(f"not ready: {url}")


async def main() -> None:
    backend_procs = []
    curl = None
    try:
        # 前置：Redis 容器
        r = subprocess.run(["docker", "exec", "course-redis", "redis-cli", "ping"], capture_output=True)
        assert b"PONG" in r.stdout, "请先启动 course-redis 容器（见 r1 README）"

        for port in (18901, 18902):
            kill_port(port)
        await asyncio.sleep(0.5)
        backend_procs.append(await serve(18901))
        backend_procs.append(await serve(18902))
        start_nginx()

        async with httpx.AsyncClient(timeout=30) as c:
            await wait_ready(c, f"http://127.0.0.1:{NGINX_PORT}/agent/tasks")
            print("[拓扑] Nginx(8080) → Worker×2(18901/18902) → Redis(6399) 已就绪\n")

            # 1) 六个任务经 Nginx 创建：负载均衡打散，Hash 让两边都可见
            tids = []
            for i in range(6):
                r = await c.post("http://127.0.0.1:8080/agent/tasks",
                                 json={"goal": f"topology-{i}"})
                assert r.status_code == 200, (
                    f"经 Nginx 创建任务失败：HTTP {r.status_code} {r.text[:200]}"
                )
                tids.append(r.json()["task_id"])
            listed_a = (await c.get("http://127.0.0.1:18901/agent/tasks")).json()
            listed_b = (await c.get("http://127.0.0.1:18902/agent/tasks")).json()
            assert set(tids) <= {t["task_id"] for t in listed_a}
            assert set(tids) <= {t["task_id"] for t in listed_b}
            print("[1] 6 个任务经 Nginx 创建，两个 Worker 都能看到全部任务（Hash）✔")

        # 2/3/4：对第一个任务做全流程（经 Nginx 的 SSE 消费 + WS 审批）
        tid = tids[0]
        sse_file = Path(tempfile.gettempdir()) / f"n2_sse_{tid}.txt"
        if sse_file.exists():
            sse_file.unlink()
        curl = await asyncio.create_subprocess_exec(
            "curl", "-s", "-N", "--max-time", "90",
            f"http://127.0.0.1:{NGINX_PORT}/agent/tasks/{tid}/events",
            stdout=open(sse_file, "wb"),
        )
        events: list[dict] = []
        seen: set[int] = set()
        tool_call_seen = False
        approved = False
        done = False
        deadline = time.time() + 80

        async with websockets.connect(f"ws://127.0.0.1:{NGINX_PORT}/ws/control") as ws:
            while time.time() < deadline and not done:
                await asyncio.sleep(0.15)
                text = sse_file.read_bytes().decode("utf-8", errors="ignore")
                for ev in parse_sse(text):
                    if ev["id"] in seen:
                        continue
                    seen.add(ev["id"])
                    events.append(ev)
                    data = {}
                    try:
                        data = json.loads(ev.get("data", "{}"))
                    except json.JSONDecodeError:
                        pass
                    if ev["event"] == "tool_call" and data.get("data", {}).get("requires_approval"):
                        tool_call_seen = True
                    if ev["event"] in ("done", "agent_error"):
                        done = True
                # 控制逻辑：看到 tool_call 后经 WS 批准（重发直到 tool_result 出现）
                if tool_call_seen and not approved:
                    await ws.send(json.dumps({"task_id": tid, "action": "approve"}))
                    approved = True
                elif approved and "tool_result" not in {e["event"] for e in events}:
                    if time.time() % 1 < 0.2:  # 每 ~1 秒重发一次
                        await ws.send(json.dumps({"task_id": tid, "action": "approve"}))

        types = [e["event"] for e in events]
        seqs = [e["id"] for e in events]
        assert types[-1] == "done", types[-4:]
        assert "tool_call" in types and "tool_result" in types, types
        assert seqs == sorted(seqs), "seq 必须单调"
        print(f"[2] 经 Nginx 的 SSE 直播 ✔ {len(events)} 条事件（创建与订阅可能落在不同 Worker）")
        print(f"[3] 经 Nginx 的 WS 审批 ✔ 工具调用被批准并执行")

        async with httpx.AsyncClient(timeout=30) as c:
            final = (await c.get(f"http://127.0.0.1:8080/agent/tasks/{tid}")).json()
        assert final["state"] == "done", final
        print(f"[4] 终态同步 ✔ 经 Nginx 查询 state=done")

        print("\n✔ 完整体系验证通过：Browser → Nginx → Worker×2 → Redis 全链路协作")
    finally:
        if curl is not None and curl.returncode is None:
            curl.kill()
        for p in backend_procs:
            if p.returncode is None:
                p.kill()
        for p in backend_procs:
            await p.wait()
        sh(["docker", "rm", "-f", "course-nginx-n2"])


if __name__ == "__main__":
    asyncio.run(main())
