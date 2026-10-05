"""n1 验证：正确配置让流活着穿过 Nginx；事故配置（read_timeout 2s）掐断它。

运行：python n1_nginx_proxy/verify_through_nginx.py   （需要 Docker）
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import websockets

# Windows 管道/重定向下 stdout 退回 GBK：print("✔") 会抛 UnicodeEncodeError 中断脚本
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

LABS = Path(__file__).resolve().parent.parent
CONF_DIR = Path(__file__).resolve().parent / "conf"
NGINX_IMAGE = "nginx:1.28-alpine"
BACKEND_PORT = 8807
NGINX_PORT = 8080


def sh(cmd: list[str]) -> None:
    subprocess.run(cmd, capture_output=True)


def docker_running(name: str) -> bool:
    """容器是否真的在跑——`docker run` 失败（端口被占）时它不会报错到我们这儿。"""
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0 and r.stdout.strip() == "true"


def kill_port(port: int) -> None:
    """清掉占住端口的旧 uvicorn 残骸。

    Windows 上验证脚本异常退出会留下孤儿进程（learning-records/0004 第 6 条）：
    新 backend 起不来 → wait_ready 命中旧进程 → 清理阶段 backend.kill() 反而抛
    ProcessLookupError，把已经跑绿的检查一起带崩。开跑前必须按端口清残。
    """
    out = subprocess.run(["netstat", "-ano"], capture_output=True).stdout.decode(
        "utf-8", errors="ignore"
    )
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            sh(["taskkill", "/PID", line.split()[-1], "/F"])


def start_nginx(conf: str) -> None:
    sh(["docker", "rm", "-f", "course-nginx-n1"])
    conf_path = str((CONF_DIR / conf).resolve()).replace("\\", "/")
    sh(["docker", "run", "-d", "--name", "course-nginx-n1", "-p", f"{NGINX_PORT}:8080",
        "-v", f"{conf_path}:/etc/nginx/conf.d/default.conf", NGINX_IMAGE])
    if not docker_running("course-nginx-n1"):
        raise RuntimeError(
            f"nginx 容器没起来：宿主 {NGINX_PORT} 很可能已被别的容器占用"
            f"（docker ps --format '{{{{.Names}}}} {{{{.Ports}}}}' 查看后 docker rm -f <名字>）"
        )


def stop_nginx() -> None:
    sh(["docker", "rm", "-f", "course-nginx-n1"])


async def wait_ready(client: httpx.AsyncClient, url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if (await client.get(url)).status_code < 500:
                return
        except httpx.HTTPError:
            await asyncio.sleep(0.2)
    raise RuntimeError(f"not ready: {url}")


async def measure_sse(client: httpx.AsyncClient) -> tuple[int, float]:
    """消费 /sse（约 5 秒流完），返回（收到的事件数，首尾时间跨度）。"""
    stamps: list[float] = []
    async with client.stream("GET", f"http://127.0.0.1:{NGINX_PORT}/sse") as r:
        async for chunk in r.aiter_text():
            stamps.append(time.monotonic())
    assert stamps, "SSE 无内容"
    return len(stamps), stamps[-1] - stamps[0]


async def test_ws() -> None:
    async with websockets.connect(f"ws://127.0.0.1:{NGINX_PORT}/ws/echo") as ws:
        await ws.send("hello via nginx")
        assert await asyncio.wait_for(ws.recv(), 5) == "hello via nginx"


async def main() -> None:
    kill_port(BACKEND_PORT)  # 清掉上一轮留下的孤儿 uvicorn，否则新进程会 bind 失败
    backend = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "uvicorn", "n1_nginx_proxy.app:app",
        "--host", "0.0.0.0", "--port", str(BACKEND_PORT), "--log-level", "error", cwd=LABS,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            await wait_ready(c, f"http://127.0.0.1:{BACKEND_PORT}/sse")
            assert backend.returncode is None, (
                f"backend 启动即退出（退出码 {backend.returncode}）——{BACKEND_PORT} 端口多半被占"
            )

            print("[1] 正确配置（n1-good.conf）：SSE 存活 + WS 透传")
            start_nginx("n1-good.conf")
            await wait_ready(c, f"http://127.0.0.1:{NGINX_PORT}/slow")
            n, span = await measure_sse(c)
            assert n >= 10, f"应收到全部 10 个事件，实际 {n}"
            assert span > 3.0, f"流式应陆续到达，跨度 {span:.2f}s"
            await test_ws()
            print(f"    {n} 个事件陆续到达（跨度 {span:.2f}s）✔ WebSocket Upgrade 透传 ✔")

            print("[2] 事故配置（n1-incident.conf）：read_timeout 2s 掐断长流")
            start_nginx("n1-incident.conf")
            await asyncio.sleep(1.5)  # 等容器起；注意不能用 /slow 探活——3s 的它自己会被 2s 超时掐成 504
            killed = False
            try:
                n2_, _span2 = await measure_sse(c)
                killed = n2_ < 10  # 若没被掐断，应收到全部 10 个事件
                if killed:
                    print(f"    只收到 {n2_} 个事件后流被提前终止 ✔")
            except (httpx.HTTPError, AssertionError):
                killed = True  # 客户端表现为连接被重置/提前结束——同样是"被掐"的形态
                print("    连接被 Nginx 提前掐断 ✔")
            assert killed, "事故配置应当在流完成前掐断连接"

        print("\n✔ 对照成立：正确配置让流完整穿过 Nginx；read_timeout 不足则静默掐断。")
        print("  这就是心跳存在的意义：15s 一条的 ': ping' 会不断重置读超时定时器。")
    finally:
        stop_nginx()
        if backend.returncode is None:  # 已自行退出时 kill() 会抛 ProcessLookupError
            backend.kill()
        await backend.wait()
    _ = json, os


if __name__ == "__main__":
    asyncio.run(main())
