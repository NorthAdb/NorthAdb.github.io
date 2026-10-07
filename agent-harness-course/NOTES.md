# NOTES（教学偏好与工作笔记）

## 用户偏好（来自首次需求说明）

- 语言：中文教学。
- 起点假设：不要当成已理解 Agent Harness 的人。第一个问题必须是"为什么 LLM 自己不能成为 Agent"。
- 每个新概念必须回答 7 问：解决什么问题 / 没有它会怎样 / 输入 / 输出 / 谁控制 / 和前一个概念的关系 / Pi 源码哪里实现。
- 每张 Archify 图之后按固定三段讲：①这张图要解决什么问题 ②如何从图上读懂 Pi ③这张图在整个学习体系中的位置。
- 不大量粘贴源码；建立「概念 → 模块 → 调用链 → 数据流」映射，伪代码 10–30 行以内。
- 明确区分三层证据：源码事实 / 官方文档 / 架构推断。
- 课程为 14 阶段固定主线（用户已给出完整大纲，见 lessons/COURSE 总纲）。
- 最终交付物：Minimal Pi-like Agent Harness 手写练习（需求→接口→数据结构→运行流程→最小实现→测试→扩展）。

## 工作笔记

- 仓库结构（已核实，1.0.2，2026-10-04）：packages/{chord, telemetry, tui, ai, durable, agent, protocol, client, server, codemode, mcp, coding-agent, evals}。没有 `session-backends`。
- 1.0.0 起 `@earendil-works/pi-agent-core` 只保留 `Agent`、循环、proxy 与类型。旧的 `packages/agent/src/harness` 与 `packages/agent/docs/` 已删除。日常 `pi` 的会话树和压缩仍在 `packages/coding-agent`。实验性持久化运行时是 `@earendil-works/pi-durable`（SQLite / JSONL 存储在该包内）。
- 2026-10 按 1.0.2 复核两套中文材料：行号、包边界、MCP 默认暴露与内置扩展清单。Diagram 08 / 12 / 14 的可见文案已改；画布布局未重排（Archify 不在本机）。
- fork 内已有 learn-pi/ 中文概览导读（22 篇），本课程不与其重复：learn-pi 是"是什么/怎么用"，本课程是"为什么这样设计 + 源码逆向"。
- Archify 图表嵌入 lessons/*.html；每个 lesson 一个主题一个图。
- 证据标注约定：【源码】【文档】【推断】。
