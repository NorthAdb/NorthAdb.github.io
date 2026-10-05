"""Agent Loop —— 对应 Pi: packages/agent/src/agent-loop.ts（本练习的心脏）

设计卷 Day 3-5 + 第 3 步流程图。把伪代码逐行变成真代码；
每个 hooks.emit 的位置和语义见 hooks.py。测试：test_02 / test_03 / test_07。
"""
from __future__ import annotations

from minimal_harness.provider import LLMProvider
from minimal_harness.session import SessionStore
from minimal_harness.tools import ToolRegistry


def agent_loop(
    context,          # Context：由调用方用 context_builder 组装好
    registry: ToolRegistry,
    provider: LLMProvider,
    session: SessionStore,
    hooks=None,
) -> str:
    """返回最终文本答复。

    流程（对照设计卷第 3 步）：
      1. should_compact? → compact()                    （第 6 步实现后启用）
      2. hooks.emit("before_llm_request", context)      （第 4 步实现后启用）
      3. msg = provider.stream(context)                 契约：失败也是消息
      4. session.append_message(msg)                    先持久化再判断
      5. 无 toolCall → 返回 msg.text（agent_end）
      6. 有 toolCall → 逐个 hooks.emit("tool_call")，可 block
      7. registry.execute(...) → toolResultMessage → append 回 context + session
      8. 回到 1（while True）
    """
    raise NotImplementedError("第 2 课：整个课程的心脏，~40 行。别抄 Pi，照着测试写")
