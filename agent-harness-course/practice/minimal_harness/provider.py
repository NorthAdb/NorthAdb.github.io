"""LLM Provider —— 对应 Pi: StreamFn 契约（agent/types.ts:33）。

契约铁律：**失败不抛异常**，而是返回 stop_reason="error" 的 AssistantMessage，
让循环把它当普通轮次处理（第 2 课：错误也是数据）。

MockProvider 已给出一个完整场景示例（loop_exit）作为模式样板；
你要照此模式补全其余场景，让 tests/test_02~07 全部可驱动。
"""
from __future__ import annotations

from minimal_harness.types import AssistantMessage, Context, ToolCall


class LLMProvider:
    def stream(self, context: Context) -> AssistantMessage:
        raise NotImplementedError


class MockProvider(LLMProvider):
    """按脚本顺序吐出预设响应 —— 测试不花钱的 Provider（设计卷 Day 2-3）。

    scenario 是一个列表：每项是 dict，支持两种形态——
      {"text": "..."}                       → 纯文本回复（循环应退出）
      {"tool_calls": [{"id","name","arguments"}]}  → 工具调用轮
    用光脚本后继续调用 → 返回 stop_reason="error"（这就是契约铁律的落点）。
    """

    def __init__(self, scenario: list[dict]):
        self.script = list(scenario)

    def stream(self, context: Context) -> AssistantMessage:
        # ── 已完成的样板：脚耗尽 → error（对应第 2 课"错误也是数据"）──
        if not self.script:
            return AssistantMessage(text="provider exhausted", stop_reason="error")

        step = self.script.pop(0)
        if "text" in step:
            # TODO(你): 返回 AssistantMessage(text=..., stop_reason="stop")
            raise NotImplementedError("第 2 课：无 toolCall 的轮次该怎么构造？")
        calls = [
            ToolCall(id=c["id"], name=c["name"], arguments=c["arguments"])
            for c in step["tool_calls"]
        ]
        # TODO(你): 返回 AssistantMessage(tool_calls=..., stop_reason="toolUse")
        raise NotImplementedError("第 2 课：toolCall 轮该怎么构造？")


class AnthropicProvider(LLMProvider):
    """真 API（选做）：调 anthropic messages API，把 stop_reason 映射成我们的枚举。

    对照 Pi: packages/ai/src/api/anthropic-messages.ts:1507 的映射表。
    没有 key 也可以毕业——MockProvider 已覆盖全部测试。
    """

    def stream(self, context: Context) -> AssistantMessage:
        raise NotImplementedError("选做：需要 API key；对照 Pi 的 stop_reason 映射表实现")
