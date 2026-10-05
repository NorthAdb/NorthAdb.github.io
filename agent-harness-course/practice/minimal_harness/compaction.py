"""Compaction —— 对应 Pi: coding-agent/src/core/compaction/compaction.ts

设计卷 Day 8-9。四个函数对应 Pi 的四个概念（第 6 课全部给了行号）：
shouldCompact:289 / isCutPoint:373 / findCutPoint:468 / SUMMARIZATION_PROMPT:529
"""
from __future__ import annotations

RESERVE_TOKENS = 4096
KEEP_RECENT_TOKENS = 3000


def estimate_tokens(text: str) -> int:
    """Pi 用 chars/4 启发式（compaction.ts:320）——你也是。"""
    raise NotImplementedError("第 6 课")


def should_compact(total_tokens: int, context_window: int,
                   reserve: int = RESERVE_TOKENS) -> bool:
    """tokens > window − reserve（compaction.ts:289）。一行。"""
    raise NotImplementedError("第 6 课")


def find_cut_index(messages: list, keep_recent_tokens: int = KEEP_RECENT_TOKENS) -> int:
    """从最新往回累计 estimate_tokens，到预算处返回切点下标。

    铁律（compaction.ts:373）：切点永远不能落在 toolResult 消息上——
    宁可多保留几条，也要保证 toolCall/toolResult 成对完整（test_05 的关键断言）。
    """
    raise NotImplementedError("第 6 课")


def compact(context, session, summarizer, window: int) -> None:
    """把切点之前的消息交给 summarizer（一个 LLMProvider）生成结构化摘要，
    在 session 落一条 compaction 条目（summary + first_kept_entry_id），
    并让 context.messages 由投影重建（摘要替换旧历史）。

    摘要模板直接抄设计卷/Pi 的 SUMMARIZATION_PROMPT 六段结构。
    """
    raise NotImplementedError("第 6 课")
