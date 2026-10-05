"""v7 全流程自动化测试：创建任务 → SSE 看直播 → WS 自动审批 → 观察终态。

先启动服务：python -m uvicorn v7_agent_server.app:app --port 8807
再运行：    python v7_agent_server/test_flow.py
"""

import asyncio
import json
import sys

import httpx
import websockets

# Windows 管道/重定向下 stdout 退回 GBK：print("✔") 会抛 UnicodeEncodeError 中断脚本
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8807"
WS_URL = "ws://127.0.0.1:8807/ws/control"


async def main() -> None:
    events: list[dict] = []
    finished = asyncio.Event()

    async with httpx.AsyncClient(base_url=BASE, timeout=60) as client:
        r = await client.post("/agent/tasks", json={"goal": "给老板发一封周报邮件"})
        task_id = r.json()["task_id"]
        print(f"[1] 创建任务 task_id={task_id}")

        async def auto_approver() -> None:
            """模拟人在回路：看到 approval_required 就批准。"""
            async with websockets.connect(WS_URL) as ws:
                while not finished.is_set():
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
                    except TimeoutError:
                        continue
                    print(f"[WS] 镜像消息: {msg}")
                    if msg.get("type") == "approval_required" and msg.get("task_id") == task_id:
                        await ws.send(json.dumps({"task_id": task_id, "action": "approve"}))
                        print("[WS] 已发送 approve")

        approver = asyncio.create_task(auto_approver())

        print("[2] 订阅 SSE 事件流 ...")
        async with client.stream("GET", f"/agent/tasks/{task_id}/events") as resp:
            buf = ""
            async for chunk in resp.aiter_text():
                buf += chunk
                while "\n\n" in buf:
                    block, buf = buf.split("\n\n", 1)
                    ev: dict = {}
                    for line in block.splitlines():
                        if line.startswith("event:"):
                            ev["type"] = line[6:].strip()
                        elif line.startswith("id:"):
                            ev["seq"] = int(line[3:].strip())
                        elif line.startswith("data:"):
                            ev.setdefault("data", "")
                            ev["data"] += line[5:].strip()
                    if not ev:
                        continue
                    events.append(ev)
                    print(f"[SSE] seq={ev.get('seq')} {ev.get('type')} {ev.get('data', '')[:60]}")

        finished.set()
        approver.cancel()

    types = [e.get("type") for e in events]
    seqs = [e.get("seq") for e in events]
    assert types[0] == "agent_started", types[:3]
    assert types[-1] == "done", types[-3:]
    assert "tool_call" in types and "tool_result" in types, types
    # SSE 的 data 是 JSON 字符串（中文可能被转义为 \uXXXX），解析后再断言字段值
    def payload(e: dict) -> dict:
        try:
            return json.loads(e.get("data", "{}"))
        except json.JSONDecodeError:
            return {}
    assert any(
        "已发送" in payload(e).get("data", {}).get("result", "")
        for e in events
        if e["type"] == "tool_result"
    ), [e for e in events if e["type"] == "tool_result"]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs), "seq 必须单调且唯一"
    print(f"\n[3] 全流程通过 ✔ 共收到 {len(events)} 条事件，seq 单调递增，工具调用被成功审批")


if __name__ == "__main__":
    asyncio.run(main())
