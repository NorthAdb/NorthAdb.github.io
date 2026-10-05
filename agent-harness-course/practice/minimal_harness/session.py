"""Session Store —— 对应 Pi: packages/coding-agent/src/core/session-manager.ts

设计卷 Day 1-2。核心思想（第 5 课）：append-only + parentId 树 + leaf 指针。
storage 形状见设计卷第 2 步（session.jsonl 每行一个 Entry）。
"""
from __future__ import annotations

from minimal_harness.types import AssistantMessage, Message, ToolResultMessage, UserMessage


class SessionStore:
    def __init__(self, path):
        """path: JSONL 文件路径。若文件已存在 → 恢复（test_01_restore）。"""
        self.path = path
        self.entries: list[dict] = []  # 每项 {type, id, parent_id, message?}
        raise NotImplementedError("第 5 课：若文件存在则逐行恢复，重建 entries")

    def append_message(self, msg: Message) -> str:
        """追加一条 message 条目，parent_id = 当前 leaf；返回新条目 id。"""
        raise NotImplementedError("第 5 课：append-only，绝不改写已有行")

    def leaf_id(self) -> str | None:
        raise NotImplementedError("第 5 课：leaf = 树的当前末端（最后一个条目）")

    def projection(self) -> list[Message]:
        """从 leaf 沿 parent_id 回溯到根，返回有序 Message 列表。

        这是"Session ≠ Context"的实现现场（第 4/5 课）。
        compaction 条目的处理在第 6 步再做（本步可忽略）。
        """
        raise NotImplementedError("第 5 课：回溯 + 还原成 UserMessage/AssistantMessage/ToolResultMessage")
