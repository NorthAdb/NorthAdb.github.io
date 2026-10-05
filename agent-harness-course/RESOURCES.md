# Agent Harness（Pi 源码逆向）Resources

## Knowledge（一手来源，全部在本地仓库内）

- [本地源码根目录](../README.md) — 主要研究对象。fork of earendil-works/pi，monorepo。
  Use for: 一切「源码事实」级结论的唯一依据。
- [packages/agent/README.md](../packages/agent/README.md) — Agent 循环与事件模型的官方说明。
  Use for: Diagram 02（Agent Loop）、loop 控制权、事件流。
- [packages/ai/README.md](../packages/ai/README.md) — 多厂商 LLM 抽象层。
  Use for: Diagram 01/03（Model Provider、Tool Schema、消息类型）。
- [packages/coding-agent/docs/](../packages/coding-agent/docs/) — coding-agent 产品层官方文档。
  Use for: Diagram 04–10（context、session、compaction、extensions、skills、modes）。
- [packages/tui/README.md](../packages/tui/README.md) — 终端 UI 框架。
  Use for: Diagram 10（TUI 与 Runtime 解耦）。
- [AGENTS.md](../AGENTS.md) + [CONTRIBUTING.md](../CONTRIBUTING.md) — 仓库自身的 Agent 规则与贡献结构。
  Use for: 理解"Pi 用自己的 Harness 开发自己"。
- [learn-pi/](../learn-pi/README.md) — fork 中已有的中文概览导读（8 个主题、22 篇）。
  Use for: 快速背景与包地图；本课程在其之上做源码级深挖，不重复它。

## Wisdom (Communities)

- [earendil-works/pi GitHub Issues & Discussions](https://github.com/earendil-works/pi)
  Use for: 设计决策的第一手讨论；作者对"为什么不做 X"的答复。
- 作者技术博客（从仓库 README / 包作者字段可追踪到 Mario Zechner / badlogic）
  Use for: Harness 设计哲学的长文论述。引用前需先从仓库内链接核实。

## Gaps

- Claude Code / Codex / OpenCode 的 Harness 层比较（第 13 阶段）缺公开源码级资料：
  Claude Code 与 Codex 官方未开放核心源码，比较将标注为「公开文档 + 公开逆向资料级别证据」，
  强度低于 Pi 的源码事实，需在课程中明确降级说明。
- 官方文档站点 pi.dev 的可达性未验证，引用前需核实。
