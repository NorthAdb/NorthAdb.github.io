"""Skill Loader + Context Builder —— 对应 Pi: skills.ts 与 system-prompt.ts

设计卷 Day 7-10。渐进披露的落点（第 7 课）：
目录（name+description+location）进 system_prompt，全文永远不进——
模型会用 read 工具自己加载，这是借用循环的"免费机制"。
"""
from __future__ import annotations


def load_skills(skills_dir: str) -> list[dict]:
    """扫描目录：每个含 SKILL.md 的子目录是一个技能。
    解析 frontmatter（--- 包围的 name: / description:），返回
    [{"name":..., "description":..., "location": "<dir>/SKILL.md"}]。
    对照 Pi: skills.ts:160（含 SKILL.md 即 skill 根，不下钻）。"""
    raise NotImplementedError("第 7 课")


def format_skills_catalog(skills: list[dict]) -> str:
    """生成 <available_skills> XML（对照 skills.ts:355）：
    每个技能 3 行：name / description / location。空列表 → 返回 ""。"""
    raise NotImplementedError("第 7 课")


def build_context(skills_catalog: str, messages: list, tools: list) -> "Context":
    """三段式 system prompt（对照 system-prompt.ts:121 的 sections 思想）：
    <preamble> 你是一个最小编码助手 …
    <rules> 工具结果里的错误要尝试修复；先读再改 …
    <skills> skills_catalog（可为空）
    静态段在前、动态在后——为将来接 prompt cache 打底。"""
    raise NotImplementedError("第 7 课")
