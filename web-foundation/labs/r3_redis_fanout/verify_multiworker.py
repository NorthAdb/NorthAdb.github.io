"""r3 双进程端到端验证：v7 在多 Worker 下必碎的三个场景，这里全部证明已修复。

  进程 A（18901）：创建任务（任务的闸门/runner 在 A）
  进程 B（18902）：SSE 订阅 + WS 控制命令 + 任务列表
  中间：真 Redis（Docker 容器 course-redis，端口 6399）

预期：B 能看到完整事件流、控制命令能跨进程送达 A 并生效。
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx
import websockets

# Windows 管道/重定向下 stdout 退回 GBK：print("✔") 会抛 UnicodeEncodeError 中断脚本
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

LABS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LABS))


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


def kill_port(port: int) -> None:
    """清掉占用端口的残留进程（Windows：netstat 找 PID → taskkill）。

    之前失败的调试过程留下的孤儿 uvicorn 会占住端口并运行旧代码——
    这是教学之外的另一课：自动化验证必须自己保证环境干净。
    """
    import subprocess

    # netstat 输出在中文 Windows 上是 GBK，按 utf-8 解会炸——端口/PID 是 ASCII，
    # 用 errors="ignore" 忽略非 ASCII 残渣即可
    out = subprocess.run(["netstat", "-ano"], capture_output=True).stdout.decode(
        "utf-8", errors="ignore"
    )
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            pid = line.split()[-1]
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)


async def serve(port: int) -> asyncio.subprocess.Process:
    import tempfile

    log = open(Path(tempfile.gettempdir()) / f"r3_server_{port}.log", "wb")
    return await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uvicorn", "r3_redis_fanout.app:app",
        "--port", str(port), "--log-level", "error",
        cwd=LABS, stdout=log, stderr=log,
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
    import os

    procs = []
    curl_proc = None
    try:
        kill_port(18901)
        kill_port(18902)
        await asyncio.sleep(0.5)
        procs.append(await serve(18901))
        procs.append(await serve(18902))
        async with httpx.AsyncClient(timeout=60) as c:
            await wait_ready(c, "http://127.0.0.1:18901/agent/tasks")
            await wait_ready(c, "http://127.0.0.1:18902/agent/tasks")

            # 场景 1：A 创建，B 可见（Hash 跨进程）
            tid = (await c.post("http://127.0.0.1:18901/agent/tasks",
                                json={"goal": "双进程验证"})).json()["task_id"]
            await asyncio.sleep(0.2)
            listed = (await c.get("http://127.0.0.1:18902/agent/tasks")).json()
            assert any(t["task_id"] == tid for t in listed), "B 看不到 A 创建的任务"
            print(f"[1] Hash 跨进程 ✔ B 看到了 A 创建的任务 {tid}")

            events: list[dict] = []
            paused_seen = asyncio.Event()
            running_seen = asyncio.Event()
            approval_needed = asyncio.Event()
            tool_result_seen = asyncio.Event()

            sse_file = Path(tempfile.gettempdir()) / f"r3_sse_{os.getpid()}.txt"
            if sse_file.exists():
                sse_file.unlink()
            curl_proc = None

            async def consume() -> None:
                """消费 B 的 SSE。

                为什么用 curl 子进程而不是 httpx 流式读取：实测 httpx 流式
                （Windows Proactor + 同循环内 websockets）在长 SSE 上偶发
                ReadError；curl -N 稳定。curl 在 Windows 10+ 自带。
                """
                nonlocal curl_proc
                try:
                    curl_proc = await asyncio.create_subprocess_exec(
                        "curl", "-s", "-N", "--max-time", "60",
                        f"http://127.0.0.1:18902/agent/tasks/{tid}/events",
                        stdout=open(sse_file, "wb"),
                    )
                    print("[B] SSE 已连接（curl 消费）")
                    parsed_seqs: set[int] = set()
                    while True:
                        await asyncio.sleep(0.15)
                        if not sse_file.exists():
                            continue
                        text = sse_file.read_bytes().decode("utf-8", errors="ignore")
                        for ev in parse_sse(text):
                            if ev["id"] in parsed_seqs:
                                continue
                            parsed_seqs.add(ev["id"])
                            events.append(ev)
                            print(f"    <- {ev['id']} {ev['event']}")
                            data = {}
                            try:
                                data = json.loads(ev.get("data", "{}"))
                            except json.JSONDecodeError:
                                pass
                            if ev["event"] == "task_state" and data.get("data", {}).get("state") == "paused":
                                paused_seen.set()
                            if ev["event"] == "task_state" and data.get("data", {}).get("state") == "running":
                                running_seen.set()
                            if ev["event"] == "tool_call" and data.get("data", {}).get("requires_approval"):
                                approval_needed.set()
                            if ev["event"] == "tool_result":
                                tool_result_seen.set()
                            if ev["event"] in ("done", "agent_error"):
                                return
                except Exception as exc:
                    print(f"    !! consumer 异常: {type(exc).__name__}: {exc}")
                    raise

            # 场景 2：B 的 SSE 订阅 + B 的 WS 命令（pause → resume → approve）
            # 注意重发：Pub/Sub 不留存消息，若命令发出时属主订阅未就绪/闸门未就绪，
            # 消息会丢失——所以真实 UI 控制都带"重发直到看到状态反馈"
            import time

            async def control() -> None:
                async with websockets.connect("ws://127.0.0.1:18902/ws/control") as ws:
                    async def send_until(action, seen, timeout: float = 30) -> None:
                        deadline = time.time() + timeout
                        while time.time() < deadline:
                            await ws.send(json.dumps({"task_id": tid, "action": action}))
                            try:
                                await asyncio.wait_for(seen.wait(), 0.6)
                                return
                            except TimeoutError:
                                continue
                        raise TimeoutError(f"命令 {action} 在 {timeout}s 内未生效")

                    await send_until("pause", paused_seen)
                    print("[2] 暂停跨进程 ✔ B 发命令 → A 的闸门生效")
                    await send_until("resume", running_seen)
                    print("[2] 恢复跨进程 ✔")
                    await asyncio.wait_for(approval_needed.wait(), 30)
                    await send_until("approve", tool_result_seen)
                    print("[2] 审批跨进程 ✔ approve 经 control 频道送达属主")

            consumer = asyncio.create_task(consume())
            controller = asyncio.create_task(control())
            await asyncio.gather(controller, consumer)

            types = [e["event"] for e in events]
            seqs = [e["id"] for e in events]
            assert types[-1] == "done", types[-4:]
            assert "task_state" in types and "tool_call" in types and "tool_result" in types
            assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs), "seq 必须单调且唯一"
            assert any(
                "已发送" in json.loads(e["data"]).get("data", {}).get("result", "")
                for e in events if e["event"] == "tool_result"
            )
            print(f"[3] 全流程跨进程 ✔ {len(events)} 条事件（含暂停/恢复/审批），seq 单调，来自 B 的视角")

            # 场景 3：终态写入 Hash，B 侧可查
            state = (await c.get(f"http://127.0.0.1:18902/agent/tasks/{tid}")).json()["state"]
            assert state == "done", state
            print("[4] 终态同步 ✔ Hash 中 state=done")
    finally:
        if curl_proc is not None and curl_proc.returncode is None:
            curl_proc.kill()
        for p in procs:
            if p.returncode is None:
                p.kill()  # terminate 在 Windows 上偶发杀不干净，kill 更彻底
            else:
                print(f"!! 子进程提前退出：returncode={p.returncode}")
        for p in procs:
            await p.wait()
        for port in (18901, 18902):
            log_path = Path(tempfile.gettempdir()) / f"r3_server_{port}.log"
            if log_path.exists() and log_path.stat().st_size > 0:
                print(f"--- server {port} 日志 ---")
                print(log_path.read_text(encoding="utf-8", errors="ignore")[:800])


if __name__ == "__main__":
    asyncio.run(main())
