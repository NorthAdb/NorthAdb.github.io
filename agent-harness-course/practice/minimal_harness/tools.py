"""Tool Registry / Execution —— 对应 Pi: coding-agent/src/core/tools/* 与 truncate.ts

设计卷 Day 3-5。三条铁律（第 3 课）：
1. 参数必须过 JSON Schema 校验，失败 → error_result，不是异常
2. 输出超 2000 行 / 50KB → 截断 + "如何继续"提示
3. execute 抛任何异常 → error_result(str(e))，循环永不被炸
"""
from __future__ import annotations

from minimal_harness.types import Tool, ToolResult

MAX_LINES = 2000
MAX_BYTES = 50 * 1024


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """重名 → raise ValueError（菜单不允许两个同名菜）。"""
        raise NotImplementedError("第 3 课")

    def get(self, name: str) -> Tool | None:
        raise NotImplementedError("第 3 课：找不到工具时循环会把它包成 error_result")

    def all(self) -> list[Tool]:
        raise NotImplementedError("第 3 课：发给模型的菜单")

    def execute(self, name: str, call_id: str, args: dict) -> ToolResult:
        """校验 → 执行 → 截断。任何失败路径都返回 ToolResult(is_error=True)。"""
        raise NotImplementedError("第 3 课：validate → execute → truncate 的三段管道")


def validate_arguments(args: dict, schema: dict) -> str | None:
    """极简 JSON Schema 校验：只要求支持 {type:object, properties, required}。
    返回 None 表示通过，否则返回错误描述。"""
    raise NotImplementedError("第 3 课：required 缺失 / 类型不符 → 返回错误描述")


def truncate(text: str, max_lines: int = MAX_LINES, max_bytes: int = MAX_BYTES) -> str:
    """保开头截断 + 尾部追加 '[Showing lines X-Y of N. ...]' 式提示（对照 read.ts:168）。"""
    raise NotImplementedError("第 3 课：读 Pi 的 read.ts 提示语怎么写")


# ── 内置工具（设计卷要求 read/write/shell 三个）──────────────────────
def make_read_tool(root: str) -> Tool: ...
def make_write_tool(root: str) -> Tool: ...
def make_shell_tool(root: str) -> Tool: ...
"""三个工厂都未实现。共同点：execute 里限制在 root 之内（对应 Pi 的 cwd 约束）；
shell 用 subprocess 且捕获超时。每个函数体 ~15 行。"""
