# Agent Harness 架构课程 · 总纲

> 浏览器友好入口：[index.html](index.html) · 研究对象：本仓库（fork of [earendil-works/pi](https://github.com/earendil-works/pi)）。
> 教学立场：不背 API，只回答"**为什么这么设计**"。所有结论标注证据等级：
> 【源码】源码可直接证明 ·【文档】官方文档证明 ·【推断】架构推断。
> 前置导读：仓库自带的 `learn-pi/`（是什么/怎么用）；本课程在其之上做"为什么 + 源码逆向"。

## 我的进度（做完一项打个 ×）

- [ ] 第 01 课 · 为什么 LLM 不是 Agent
- [ ] 第 02 课 · Agent Loop
- [ ] 第 03 课 · Tool Calling
- [ ] 第 04 课 · Context Assembly
- [ ] 第 05 课 · Session / State
- [ ] 第 06 课 · Compaction
- [ ] 第 07 课 · Skills
- [ ] 第 08 课 · Extensions
- [ ] 第 09 课 · 权限与沙箱
- [ ] 第 10 课 · TUI / RPC / SDK
- [ ] 第 11 课 · 完整 Runtime 总时序
- [ ] 第 12 课 · 通用 Harness 抽象
- [ ] 第 13 课 · 横向比较
- [ ] 第 14 课 · 五层 Mental Model
- [ ] 第 15 课（进阶） · MCP 深潜
- [ ] 毕业练习 · practice/ 17 测试全绿

## 课程地图（14 课 + 1 进阶）

| 课 | 主题 | 图 | 一句话问题 |
|----|------|-----|-----------|
| [0001](lessons/0001-why-llm-is-not-agent.html) | 为什么 LLM 不是 Agent | [01](lessons/diagrams/01-harness-overview.html) | Harness 到底比 LLM 多了什么？ |
| [0002](lessons/0002-agent-loop.html) | Agent Loop | [02](lessons/diagrams/02-agent-loop.html) | 循环由谁控制？何时结束？ |
| [0003](lessons/0003-tool-calling.html) | Tool Calling / Execution | [03](lessons/diagrams/03-tool-calling.html) | 模型看到什么？Runtime 执行什么？ |
| [0004](lessons/0004-context-assembly.html) | Context Assembly | [04](lessons/diagrams/04-context-assembly.html) | Context 如何形成？Session ≠ Context？ |
| [0005](lessons/0005-session-tree.html) | Session / State | [05](lessons/diagrams/05-session-tree.html) | 为什么需要历史树而不是 messages[]？ |
| [0006](lessons/0006-compaction.html) | Compaction | [06](lessons/diagrams/06-compaction.html) | 压缩为什么是状态压缩而非删消息？ |
| [0007](lessons/0007-skills.html) | Skills / 渐进披露 | [07](lessons/diagrams/07-skills.html) | 为什么不全量注入？ |
| [0008](lessons/0008-extensions.html) | Extensions / Hooks | [08](lessons/diagrams/08-extensions.html) | 为什么功能不进 Core？ |
| [0009](lessons/0009-capability-boundary.html) | 权限与沙箱 | [09](lessons/diagrams/09-capability-boundary.html) | Capability / Authorization / Sandbox 差在哪？ |
| [0010](lessons/0010-interfaces.html) | TUI / RPC / SDK | [10](lessons/diagrams/10-interfaces.html) | 为什么接口不能和 Runtime 写死？ |
| [0011](lessons/0011-full-runtime.html) | 完整 Runtime 总时序 | [11](lessons/diagrams/11-full-runtime.html) | 一次真实任务如何流过所有层？ |
| [0012](lessons/0012-generic-harness.html) | 通用 Agent Harness 抽象 | [12](lessons/diagrams/12-generic-harness.html) | 哪些是通用需求，哪些是 Pi 的选择？ |
| [0013](lessons/0013-comparison.html) | 横向比较 | — | 各家在"Core vs Harness"边界上的分歧 |
| [0014](lessons/0014-mental-model.html) | 五层 Mental Model | [13](lessons/diagrams/13-mental-model.html) | Agent = LLM + Loop + Harness + Environment 成立吗？ |
| [0015](lessons/0015-mcp.html) | **进阶** · MCP 深潜 | [14](lessons/diagrams/14-mcp-bridge.html) | MCP 是什么？Pi 如何以可替换的内置扩展接入？归属层级怎么判？ |

最终练习：[从 0 手写 Minimal Pi-like Agent Harness](reference/minimal-harness.html)，配套可运行工作区 [practice/](practice/README.md)（接口 + 17 个验收测试已就位，实现留给你）。
随查随用：[术语表](reference/glossary.html) · [关键源码地图](reference/source-map.html) · [一页纸速查表](reference/cheatsheet.html) · [图库](diagrams.html)。

## 后续编排（如何用完这套课程）

1. **逐课推进**：读完一课 → 做课末检索测验（先凭记忆）→ 通过导师追问后进入下一课。
2. **写学习记录**：每当"证明了一个理解 / 纠正了一个误解 / 声明了已有知识"，在
   [learning-records/](learning-records/README.md) 增加一条 `NNNN-slug.md`——这是跨会话计算你最近发展区的依据。
3. **毕业练习**：读完第 14 课后进入 `practice/`，按 README 的 6 步实现顺序把 17 个测试逐个变绿。
4. **完成标志**：设计卷末尾的七条自查全部回答"是"，并能对照 Diagram 01 向他人讲清整个 Harness。

## 学习方式

- 每课 15–25 分钟：一张聚焦图（8–12 节点）+ 三段图解 + 七问 + 源码映射 + 检索练习。
- 图表用 Archify 生成，全部通过 9 项 showcase 校验与浏览器视口检查；规格文件在
  `assets/diagrams/specs/`，可自行修改重渲染。
- 每课结尾的测验是**检索练习**：先凭记忆回答，再对照正文——这是长期记忆的关键。

## 证据基准

所有 Pi 侧结论基于当前 checkout，上游 **1.0.2**（2026-10-04）。
1.0.0 把实验性 AgentHarness 从 `packages/agent` 删除；产品会话仍是 coding-agent 的 JSONL 树，实验持久化在 `packages/durable`。
合并上游大版本后，被改动机制对应的课需要重新审计行号。
第 13 课比较 Claude Code / Codex / OpenCode 时只有公开文档级证据，会明确降级标注。
