"""Extension Hooks —— 对应 Pi: extensions/types.ts 的两个钩子 + runner.ts

设计卷 Day 7。只有两个事件，但语义必须与 Pi 一致：
- before_llm_request：处理器按序改写 context（链式），返回 None 表示不改
- tool_call：任一处理器返回 {"block": True, "reason": ...} → 本次调用被拒绝
"""
from __future__ import annotations


class HookBus:
    def __init__(self):
        self._handlers: dict[str, list] = {}

    def on(self, event: str, handler) -> None:
        raise NotImplementedError("第 8 课：注册处理器；同一事件可多个，按序执行")

    def emit_before_llm_request(self, context):
        """链式改写：handler(context) 可返回新的 context 或 None。"""
        raise NotImplementedError("第 8 课")

    def emit_tool_call(self, call: dict) -> dict | None:
        """任一处理器返回 {"block": True, "reason": str} → 立即短路返回它；
        全部放行 → 返回 None。"""
        raise NotImplementedError("第 8 课：permission-gate 的接缝就在这")
