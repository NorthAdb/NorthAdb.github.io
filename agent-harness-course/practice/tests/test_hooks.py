"""Extension Hook —— 第 8 课（tool_call 可 block；before_llm_request 可改写）。"""
from minimal_harness.types import Context, ToolCall


class TestHooks:
    def test_tool_call_block(self):
        from minimal_harness.hooks import HookBus

        bus = HookBus()
        bus.on("tool_call", lambda call: (
            {"block": True, "reason": "rm 被禁止"}
            if "rm" in call.get("arguments", {}).get("cmd", "")
            else None
        ))
        verdict = bus.emit_tool_call(
            {"id": "c1", "name": "shell", "arguments": {"cmd": "rm -rf /"}}
        )
        assert verdict and verdict["block"] and "rm" in verdict["reason"]

    def test_tool_call_pass(self):
        from minimal_harness.hooks import HookBus

        bus = HookBus()
        bus.on("tool_call", lambda call: None)
        assert bus.emit_tool_call({"id": "c1", "name": "read", "arguments": {}}) is None

    def test_before_llm_request_chain(self):
        from minimal_harness.hooks import HookBus

        bus = HookBus()
        bus.on("before_llm_request", lambda ctx: Context(
            system_prompt=ctx.system_prompt + "[A]", messages=ctx.messages))
        bus.on("before_llm_request", lambda ctx: Context(
            system_prompt=ctx.system_prompt + "[B]", messages=ctx.messages))
        ctx = bus.emit_before_llm_request(Context(system_prompt="base"))
        assert ctx.system_prompt == "base[A][B]"


class TestLoopWithHook:
    def test_blocked_call_becomes_error_result(self, tmp_path):
        """第 8/9 课：block 的结果是一条 error toolResult（不是异常、不是终止）。"""
        from minimal_harness.loop import agent_loop
        from minimal_harness.hooks import HookBus
        from minimal_harness.provider import MockProvider
        from minimal_harness.session import SessionStore
        from minimal_harness.tools import ToolRegistry

        reg = ToolRegistry(); reg.register(
            Tool := __import__("minimal_harness.types", fromlist=["Tool"]).Tool(
                name="shell", description="s",
                parameters={"type": "object", "properties": {}, "required": []},
                execute=lambda cid, args: type(
                    "R", (), {"content": "ran", "is_error": False})(),
            )
        )
        bus = HookBus()
        bus.on("tool_call", lambda call: {"block": True, "reason": "禁止 shell"})
        session = SessionStore(tmp_path / "s.jsonl")
        session.append_message(
            __import__("minimal_harness.types", fromlist=["UserMessage"]).UserMessage(
                content="hi"))
        provider = MockProvider([
            {"tool_calls": [{"id": "c1", "name": "shell", "arguments": {}}]},
            {"text": "understood"},
        ])
        ctx = Context(system_prompt="t", messages=session.projection(), tools=reg.all())
        assert agent_loop(ctx, reg, provider, session, hooks=bus) == "understood"
        errs = [m for m in session.projection()
                if getattr(m, "is_error", False)]
        assert errs and "禁止 shell" in errs[0].content
