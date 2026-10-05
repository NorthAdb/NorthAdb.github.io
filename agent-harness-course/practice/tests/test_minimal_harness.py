"""毕业练习验收测试 —— 对应设计卷第 5 步的七组用例。
全红是起点；实现顺序见 README.md。"""
import json

import pytest

from minimal_harness.types import (
    AssistantMessage, Context, Tool, ToolCall, ToolResultMessage, UserMessage,
)


def make_tool(name="read", fn=None):
    def default_execute(call_id, args):
        return type("R", (), {"content": "ok", "is_error": False})()
    return Tool(
        name=name,
        description=f"test {name}",
        parameters={"type": "object", "properties": {}, "required": []},
        execute=fn or default_execute,
    )


# ─────────────────────────── 1. Session Store ───────────────────────────
class TestSessionStore:
    def test_append_and_projection(self, tmp_path):
        """第 5 课：append-only；leaf=最后一条；投影按序还原。"""
        from minimal_harness.session import SessionStore
        s = SessionStore(tmp_path / "session.jsonl")
        s.append_message(UserMessage(content="hi"))
        s.append_message(AssistantMessage(text="hello"))
        s.append_message(ToolResultMessage(tool_call_id="c1", content="ok"))
        assert s.leaf_id() is not None
        proj = s.projection()
        assert isinstance(proj[0], UserMessage) and proj[0].content == "hi"
        assert isinstance(proj[1], AssistantMessage) and proj[1].text == "hello"
        assert isinstance(proj[2], ToolResultMessage)

    def test_restore_from_disk(self, tmp_path):
        """第 5 课：崩溃恢复——从 JSONL 重放还原（先持久化再思考）。"""
        from minimal_harness.session import SessionStore
        p = tmp_path / "session.jsonl"
        lines = [
            {"type": "session", "id": "s0", "parent_id": None},
            {"type": "message", "id": "e1", "parent_id": "s0",
             "message": {"role": "user", "content": "hi"}},
            {"type": "message", "id": "e2", "parent_id": "e1",
             "message": {"role": "assistant", "text": "hello", "tool_calls": [],
                         "stop_reason": "stop"}},
        ]
        p.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
        s = SessionStore(p)
        proj = s.projection()
        assert proj[0].content == "hi" and proj[1].text == "hello"
        assert s.leaf_id() == "e2"


# ─────────────────────────── 2. Loop 退出 ───────────────────────────
class TestLoopExit:
    def test_no_tool_call_ends(self, tmp_path):
        """第 2 课：无 toolCall 且队列空 → agent_end，返回最终文本。"""
        from minimal_harness.loop import agent_loop
        from minimal_harness.provider import MockProvider
        from minimal_harness.session import SessionStore
        from minimal_harness.tools import ToolRegistry

        reg = ToolRegistry(); reg.register(make_tool())
        session = SessionStore(tmp_path / "s.jsonl")
        session.append_message(UserMessage(content="hi"))
        provider = MockProvider([
            {"tool_calls": [{"id": "c1", "name": "read", "arguments": {}}]},
            {"text": "done"},
        ])
        ctx = Context(system_prompt="t", messages=session.projection(),
                      tools=reg.all())
        final = agent_loop(ctx, reg, provider, session)
        assert final == "done"
        assert any(isinstance(m, ToolResultMessage) for m in session.projection())


# ─────────────────────────── 3. 工具报错 ───────────────────────────
class TestToolError:
    def test_execute_exception_becomes_error_message(self, tmp_path):
        """第 2/3 课：工具抛异常 → isError toolResult 回给模型，循环继续。"""
        from minimal_harness.loop import agent_loop
        from minimal_harness.provider import MockProvider
        from minimal_harness.session import SessionStore
        from minimal_harness.tools import ToolRegistry

        def boom(call_id, args):
            raise FileNotFoundError("no such file")

        reg = ToolRegistry(); reg.register(make_tool("read", boom))
        session = SessionStore(tmp_path / "s.jsonl")
        session.append_message(UserMessage(content="hi"))
        provider = MockProvider([
            {"tool_calls": [{"id": "c1", "name": "read", "arguments": {}}]},
            {"text": "recovered"},
        ])
        ctx = Context(system_prompt="t", messages=session.projection(), tools=reg.all())
        assert agent_loop(ctx, reg, provider, session) == "recovered"
        errs = [m for m in session.projection()
                if isinstance(m, ToolResultMessage) and m.is_error]
        assert errs and "no such file" in errs[0].content

    def test_unknown_tool_is_error_not_crash(self, tmp_path):
        from minimal_harness.loop import agent_loop
        from minimal_harness.provider import MockProvider
        from minimal_harness.session import SessionStore
        from minimal_harness.tools import ToolRegistry

        reg = ToolRegistry()  # 空注册表
        session = SessionStore(tmp_path / "s.jsonl")
        session.append_message(UserMessage(content="hi"))
        provider = MockProvider([
            {"tool_calls": [{"id": "c1", "name": "ghost", "arguments": {}}]},
            {"text": "ok"},
        ])
        ctx = Context(system_prompt="t", messages=session.projection(), tools=reg.all())
        assert agent_loop(ctx, reg, provider, session) == "ok"


# ─────────────────────────── 4. 截断 ───────────────────────────
class TestTruncate:
    def test_long_output_truncated_with_hint(self):
        """第 3 课：>2000 行 → 截断 + 继续读取提示（对照 read.ts:168）。"""
        from minimal_harness.tools import truncate
        text = "\n".join(f"line {i}" for i in range(3000))
        out = truncate(text)
        assert len(out.splitlines()) < 3000
        assert "2000" in out or "offset" in out or "继续" in out or "Showing" in out

    def test_bytes_cap(self):
        from minimal_harness.tools import truncate
        out = truncate("x" * (60 * 1024))
        assert len(out.encode("utf-8")) <= 50 * 1024


# ─────────────────────────── 5. Compaction ───────────────────────────
class TestCompaction:
    def test_should_compact_threshold(self):
        from minimal_harness.compaction import should_compact
        assert should_compact(9000, 10000, reserve=4096) is True
        assert should_compact(5000, 10000, reserve=4096) is False

    def test_cut_never_splits_tool_pair(self):
        """第 6 课铁律：切点绝不落在 toolResult 上（toolCall/Result 成对完整）。"""
        from minimal_harness.compaction import find_cut_index
        msgs = []
        for i in range(6):
            msgs.append(UserMessage(content="u" * 200))             # ~50 tok
            msgs.append(ToolResultMessage(content="t" * 200))       # ~50 tok
        cut = find_cut_index(msgs, keep_recent_tokens=120)
        assert cut is not None and 0 < cut < len(msgs)
        assert not isinstance(msgs[cut], ToolResultMessage)

    def test_compact_replaces_projection(self, tmp_path):
        from minimal_harness.compaction import compact
        from minimal_harness.provider import MockProvider
        from minimal_harness.session import SessionStore

        session = SessionStore(tmp_path / "s.jsonl")
        msgs = []
        for i in range(4):
            session.append_message(UserMessage(content="u" * 400))
            session.append_message(ToolResultMessage(content="t" * 400))
        ctx = Context(system_prompt="t", messages=session.projection())
        summarizer = MockProvider([{"text": "## Goal\n压缩测试"}])
        compact(ctx, session, summarizer, window=1000)
        assert any(e.get("type") == "compaction" for e in session.entries)
        # 摘要内容必须出现在模型可见范围内（system_prompt 或任一条消息）
        visible = ctx.system_prompt + "".join(str(m) for m in ctx.messages)
        assert "压缩测试" in visible
        assert len(ctx.messages) < 8
