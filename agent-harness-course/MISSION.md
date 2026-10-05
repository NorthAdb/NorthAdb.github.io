# Mission: Agent Harness 架构设计（以 Pi 源码为工程样本）

## Why

用户想从"会使用 Coding Agent"进阶到"能设计 Agent Harness"：以 Pi（本仓库，fork of earendil-works/pi）的真实源码为逆向工程样本，反向理解一个现代 Agent Harness 为了让 LLM 稳定、持续、安全地完成复杂任务，到底需要哪些基础机制。最终检验标准：不看任何现成 Agent 的宣传页面，从一个空白目录开始，自己设计并手写一个最小可用的 Pi-like Agent Harness。

## Success looks like

- 能对照 Pi 源码，讲清 Agent Loop / Tool Calling / Tool Execution / Context Assembly / Session / Compaction / Skills / Extensions / 权限 / TUI-RPC-SDK 各机制"为什么存在"，并指出对应源码目录与调用链
- 能为每个机制画一张 8–12 节点的聚焦图（Archify），并严格区分「源码事实 / 官方文档 / 架构推断」
- 能完成"从 0 手写 Minimal Pi-like Agent Harness"练习：LLM Provider、Agent Loop、Tool Registry、Tool Execution、Context Builder、Session Store、Compaction、Skill Loader、Extension Hook
- 能就"哪些进 Core、哪些留给 Harness / Extension"对 Pi / Claude Code / Codex / OpenCode 做出有依据的横向比较，并形成 5 层 Mental Model（Model → Agent Loop → Runtime → Harness → Environment）

## Constraints

- 第一原则：以本仓库源码为依据；结论必须标注「源码事实 / 官方文档 / 架构推断」，不为图的完整性虚构组件
- 图表一律用 Archify 生成；每次一张聚焦图，8–12 节点，一条 Primary Path；禁止巨型 spaghetti 架构图
- 教学语言：中文；教学对象按"未系统理解 Agent Harness"起步，从"为什么 LLM 自己不能成为 Agent"讲起
- 学习内容全部放在本目录（agent-harness-course/），不修改仓库已有的 learn-pi/ 导读
- Pi 当前实现中没有的能力，单独标注「通用 Agent Harness 概念，不代表 Pi 当前实现」

## Out of scope

- Pi 的安装、配置、日常使用技巧（已有 learn-pi/ 概览导读覆盖）
- Prompt engineering 技巧与模型评测排行榜
- 多模态 / 语音 / 浏览器操作等非 Coding Agent 主线能力
