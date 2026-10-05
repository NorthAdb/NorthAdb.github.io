"""把工作区里的 markdown 文档渲染成与课程同款样式的 HTML 页。

用法（工作区根目录）：
    python tools/build_docs.py            # 全量重建
    python tools/build_docs.py course/module-2-流式传输与SSE.md   # 只重建指定文件

约定：
- .md 是唯一事实来源；生成物是同目录同名 .html，不要手改生成物
- 生成页自带 assets/course.css 样式与 assets/nav.js 侧栏目录（course/ 下的讲义还有上一篇/下一篇）
- 文档内的相对链接会被重写：xxx.md → xxx.html，目录链接 xxx/ → xxx/README.html
- 新增讲义/README 时，把 (源路径, 栏目标识) 加进 BUILD 列表即可
"""

import re
import sys
from pathlib import Path

import markdown

# Windows 管道/重定向下 stdout 退回 GBK：print("✔") 会抛 UnicodeEncodeError 而中断构建。
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# (源文件相对路径, 页面栏目标识, 翻页轨道)
BUILD = [
    ("COURSE.md", "课程总纲", ""),
    ("GLOSSARY.md", "术语表", ""),
    ("README.md", "工作区导航", ""),
    ("MISSION.md", "学习使命", ""),
    ("RESOURCES.md", "资源清单", ""),
    ("SSE_WebSocket_FastAPI_完整学习路线.md", "知识底稿", ""),
    ("course/module-0-为什么需要网络通信.md", "讲义 · 模块 0", "readings"),
    ("course/module-1-异步与HTTP地基.md", "讲义 · 模块 1", "readings"),
    ("course/module-2-流式传输与SSE.md", "讲义 · 模块 2", "readings"),
    ("course/module-3-WebSocket双向通信.md", "讲义 · 模块 3", "readings"),
    ("course/module-4-LLM流式与Agent事件.md", "讲义 · 模块 4", "readings"),
    ("course/module-5-综合项目与生产化.md", "讲义 · 模块 5", "readings"),
    ("course/module-6-Redis事件总线.md", "讲义 · 模块 6", "readings"),
    ("course/module-7-Nginx与部署.md", "讲义 · 模块 7", "readings"),
    ("course/appendix-troubleshooting.md", "排障附录", "readings"),
    ("labs/README.md", "实验区", ""),
    ("labs/a1_async/README.md", "实验 · A1", ""),
    ("labs/v0_hello_api/README.md", "实验 · v0", ""),
    ("labs/v2_streaming/README.md", "实验 · v2", ""),
    ("labs/v3_sse/README.md", "实验 · v3", ""),
    ("labs/v4_websocket/README.md", "实验 · v4", ""),
    ("labs/v5_llm_stream/README.md", "实验 · v5", ""),
    ("labs/v6_agent_events/README.md", "实验 · v6", ""),
    ("labs/v7_agent_server/README.md", "实验 · v7", ""),
    ("labs/r1_redis_tasks/README.md", "实验 · r1", ""),
    ("labs/r2_redis_stream/README.md", "实验 · r2", ""),
    ("labs/r3_redis_fanout/README.md", "实验 · r3", ""),
    ("labs/n1_nginx_proxy/README.md", "实验 · n1", ""),
    ("labs/n2_full_stack/README.md", "实验 · n2", ""),
    ("labs/v8_production/README.md", "实验 · v8", ""),
]

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title} · 从 HTTP 到实时 Agent Server</title>
<link rel="stylesheet" href="{base}assets/course.css">
</head>
<body>
<div class="kicker">{kicker}</div>
<h1>{title}</h1>
{body}
<footer>本页由 markdown 源文件 <code>{src}</code> 自动生成——修改源文件后运行 <code>python tools/build_docs.py</code> 重新生成。</footer>
<script src="{base}assets/nav.js" data-base="{base}" data-track="{track}"></script>
</body>
</html>
"""


def rewrite_links(md_text: str) -> str:
    """把文档内的相对链接改写为渲染后的形态。"""
    # 目录链接（指向目录的相对链接）→ 指向该目录的 README.html
    md_text = re.sub(r"\(((?!https?://|mailto:|#)[^)#]+/)\)", r"(\1README.html)", md_text)
    # 同名 markdown → html（含 # 锚点）
    md_text = re.sub(r"\(((?!https?://|mailto:)[^)#]+)\.md(#[^)]*)?\)", r"(\1.html\2)", md_text)
    return md_text


def extract_title(md_text: str) -> tuple[str, str]:
    """取第一个 '# ' 一级标题作为页面标题，并从正文中移除（模板会渲染 h1）。"""
    lines = md_text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            rest = "\n".join(lines[:i] + lines[i + 1 :])
            return title, rest.lstrip("\n")
    raise ValueError("文档缺少一级标题（# …）")


def base_for(src_rel: str) -> str:
    depth = len(Path(src_rel).parent.parts) if str(Path(src_rel).parent) != "." else 0
    return "../" * depth


def build(src_rel: str, kicker: str, track: str) -> Path:
    src = ROOT / src_rel
    out = src.with_suffix(".html")
    md_text = rewrite_links(src.read_text(encoding="utf-8"))
    title, body_md = extract_title(md_text)
    body = markdown.markdown(body_md, extensions=["tables", "fenced_code", "sane_lists"])
    base = base_for(src_rel)
    html = TEMPLATE.format(
        title=title, kicker=kicker, body=body, base=base, track=track, src=src_rel
    )
    out.write_text(html, encoding="utf-8")
    return out


def main(targets: list[str]) -> None:
    selected = (
        [b for b in BUILD if b[0] in targets]
        if targets
        else BUILD
    )
    missing = set(targets) - {b[0] for b in BUILD}
    if missing:
        print(f"未知文档：{sorted(missing)}")
        sys.exit(2)
    for src_rel, kicker, track in selected:
        out = build(src_rel, kicker, track)
        print(f"  ✔ {src_rel} → {out.relative_to(ROOT)}")
    print(f"完成：{len(selected)} 页")


if __name__ == "__main__":
    main(sys.argv[1:])
