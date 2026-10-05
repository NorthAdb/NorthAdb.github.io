"""演示入口：把九个组件接成一条可运行的命令。

实现完 core 之后，跑 `python -m minimal_harness.cli "列出当前目录的文件"`，
你的 Harness 就第一次真正开口说话了。本文件也是 stub——接线本身是练习的一部分
（对照 Pi: main.ts → createAgentSession 的组装顺序，见第 10 课）。
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m minimal_harness.cli \"<你的任务>\"")
        raise SystemExit(2)

    task = sys.argv[1]
    root = Path.cwd()

    # TODO(第 10 课)：按 sdk.ts 的组装顺序接线——
    #   registry = ToolRegistry(); registry.register(make_read_tool(root)) ...
    #   session  = SessionStore(root / ".mh-session.jsonl")
    #   provider = MockProvider(你的脚本) 或 AnthropicProvider()
    #   hooks    = HookBus()（可选挂 permission-gate）
    #   context  = build_context(format_skills_catalog(load_skills(root / "skills")),
    #                            session.projection(), registry.all())
    #   agent_loop(context, registry, provider, session, hooks)
    #   打印最终答复 + session 文件位置
    raise NotImplementedError("第 10 课：接线是最后一块拼图")


if __name__ == "__main__":
    main()
