# Minimal Harness 毕业练习 · 工作区

> 配套设计卷：[../reference/minimal-harness.html](../reference/minimal-harness.html)（先读它）
> 规则：**接口已给定，实现必须你自己写**。每个 `raise NotImplementedError` 都标注了对应课程；
> 卡住时先回课程看 Pi 的真实源码，再回来写。测试就是你的验收标准。

## 环境

```bash
cd practice
pip install -r requirements.txt        # 只有 pytest
pytest -q                              # 全部红 → 逐个变绿
```

## 建议实现顺序（每步都让一部分测试变绿）

| 步 | 文件 | 对应测试 | 课程 |
|----|------|----------|------|
| 1 | `minimal_harness/session.py` | `test_01_session_*` | [第 5 课](../lessons/0005-session-tree.html) |
| 2 | `minimal_harness/provider.py` | `test_02_*` 依赖的 mock | [第 2 课](../lessons/0002-agent-loop.html) |
| 3 | `minimal_harness/loop.py` + `tools.py` | `test_02_loop_exit` / `test_03_tool_error` / `test_04_truncate` | [第 2/3 课](../lessons/0002-agent-loop.html) |
| 4 | `minimal_harness/hooks.py` | `test_07_hook_block` | [第 8 课](../lessons/0008-extensions.html) |
| 5 | `minimal_harness/compaction.py` | `test_05_compaction` | [第 6 课](../lessons/0006-compaction.html) |
| 6 | `minimal_harness/skills.py` + `context_builder.py` | `test_06_skill_catalog` | [第 7 课](../lessons/0007-skills.html) |

## 唯一的"作弊规则"

允许随时打开 Pi 源码对照（这正是本仓库的价值），但**每写完一个函数，合上参考，能向空气讲出"为什么这么设计"**，才允许进入下一个。
七条灵魂自查见 [设计卷自查清单](../reference/minimal-harness.html)。
