"""核心数据结构 —— 已给定（对应 Pi: packages/ai/src/types.ts 与 agent/types.ts）。

读懂三个设计决定（这是你第 1 课的作业，不是代码作业）：
1. Tool 只有声明，没有 execute —— 菜单与厨房分离（第 3 课）。
2. ToolResultMessage 的 is_error 只是数据，不是异常 —— 错误也是消息（第 2 课）。
3. Context 是"本轮送进模型的全部"—— 它永远是从 Session 投影出来的（第 4/5 课）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class UserMessage:
    role: str = "user"
    content: str = ""


@dataclass
class AssistantMessage:
    role: str = "assistant"
    text: str = ""
    tool_calls: list["ToolCall"] = field(default_factory=list)
    stop_reason: str = "stop"  # stop | toolUse | length | error


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResultMessage:
    role: str = "toolResult"
    tool_call_id: str = ""
    tool_name: str = ""
    content: str = ""
    is_error: bool = False


Message = UserMessage | AssistantMessage | ToolResultMessage


@dataclass
class Tool:
    """声明（进模型菜单）+ 执行体（由注册方注入）——对应 Pi 的 Tool 与 AgentTool 之别。"""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    execute: Callable[[str, dict[str, Any]], "ToolResult"]


@dataclass
class ToolResult:
    content: str
    is_error: bool = False


@dataclass
class Context:
    """本轮送进模型的信息 —— 对应 Pi: ai/src/types.ts:697"""

    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)
