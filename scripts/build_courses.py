"""三个课程区块的同步构建，源仓库即唯一事实来源：

- agent-harness-course/  ← pi-agent-north@course 拷贝 + 主题注入 + 链接改写
- learn-pi/              ← pi-agent-north@course learn-pi/*.md 渲染（阅读顺序取自 README 课表）
- web-foundation/        ← web_fundation（先跑仓库自带 tools/build_docs.py，再拷贝 + 主题注入）

输出确定性：一律 LF、排序遍历、主题注入幂等；同步维护 search.json / sitemap.xml
中三个区块的条目。CI（deploy.yml）先 clone 两个源仓库再运行本脚本。
"""

import json
import posixpath
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote as url_quote

import markdown

# 读入的一切文本归一化：\r\n → LF、剔除 NUL（与 build_ai_engineer/build_notes 一致）
_orig_read_text = Path.read_text
def _read_text_lf(self, *a, **kw):
    return _orig_read_text(self, *a, **kw).replace("\r\n", "\n").replace("\x00", "")
Path.read_text = _read_text_lf

SITE = Path(__file__).resolve().parent.parent
WORKSPACE = SITE.parent
PI = WORKSPACE / "pi-agent-north"          # branch: course
WF = WORKSPACE / "web_fundation"

SITE_URL = "https://northadb.github.io"
PI_BLOB = "https://github.com/NorthAdb/pi-agent-north/blob/main"
TODAY = "2026-10-07"

MD_EXTS = ["extra", "sane_lists"]

# ---------------------------------------------------------------- 主题注入

THEME_PREFILL = ('<script>try{var t=localStorage.getItem("theme");'
                 'if(t)document.documentElement.setAttribute("data-theme",t);}catch(e){}</script>')
THEME_TOGGLE = (
    '<button id="themeToggle" aria-label="切换主题" style="position:fixed;top:14px;right:14px;'
    'z-index:999;width:34px;height:34px;border-radius:8px;border:1px solid rgba(127,127,127,.45);'
    'background:rgba(127,127,127,.14);color:inherit;cursor:pointer;display:grid;place-items:center;'
    'font-size:15px;line-height:1;">☾</button>\n'
    '<script>(function(){var b=document.getElementById("themeToggle");if(!b)return;'
    'function cur(){var t=document.documentElement.getAttribute("data-theme");if(t)return t;'
    'try{return localStorage.getItem("theme")||(matchMedia("(prefers-color-scheme: dark)").matches'
    '?"dark":"light")}catch(e){return "light"}}'
    'function paint(){b.textContent=cur()==="dark"?"☀":"☾"}'
    'b.addEventListener("click",function(){var n=cur()==="dark"?"light":"dark";'
    'document.documentElement.setAttribute("data-theme",n);'
    'try{localStorage.setItem("theme",n)}catch(e){}paint()});paint()})();</script>')


def theme_inject(html):
    """幂等注入主题预置脚本与切换按钮；返回 None 表示已注入过或不适用。
    只有使用课程设计系统（course.css / learn-pi/style.css）的文档页才注入，
    图表页与交互实验页有自己的内联样式，历史上也不带主题按钮。"""
    if 'id="themeToggle"' in html:
        return None
    if "course.css" not in html and "learn-pi/style.css" not in html:
        return None
    html = html.replace("</head>", THEME_PREFILL + "\n</head>", 1)
    html = html.replace("</body>", THEME_TOGGLE + "\n</body>", 1)
    return html


# ---------------------------------------------------------------- 链接改写

REPO_SRC = r"(?:packages|scripts|docs|examples|nix)"


def rewrite_links(html):
    """pi-agent-north 课程内容的站内链接改写（对 md 渲染产物与拷贝的 html 同样适用）"""
    def blob_or_tree(m):
        # 有扩展名的路径指文件（blob），无扩展名指目录（tree）
        kind = "tree" if not Path(m.group(2)).suffix else "blob"
        return f'href="{PI_BLOB.replace("/blob/main", "")}/{kind}/main/{m.group(2)}"'
    # learning-records 不发布：整条入口先移除（在链接改写之前，避免 href 被先行替换）
    html = re.sub(r'\s*<a class="pill" href="learning-records/README\.md">[^<]*</a>', "", html)
    # 仓库源码/文档相对链接 → GitHub blob/tree（learn-pi/、agent-harness-course/ 是站内内容，除外）
    html = re.sub(rf'href="((?:\.\./)+)({REPO_SRC}/[^"]+)"', blob_or_tree, html)
    html = re.sub(rf'href="((?:\.\./)+)((?:README|AGENTS|CONTRIBUTING|SECURITY)\.md)"',
                  rf'href="{PI_BLOB}/\2"', html)
    # learning-records 只存在于 course 分支且不在站点发布，指回 GitHub（README 归一化为目录）
    lr_url = f"{PI_BLOB.replace('/blob/main', '')}/tree/course/agent-harness-course/learning-records"
    html = re.sub(r'href="((?:\.\./)*)learning-records/README\.(?:md|html)"', f'href="{lr_url}"', html)
    html = re.sub(r'href="((?:\.\./)*)learning-records/([^"]+)"',
                  rf'href="{lr_url}/\2"', html)
    # learning-records 不发布：整条入口移除
    html = re.sub(r'\s*<a class="pill" href="learning-records/README\.md">[^<]*</a>', "", html)
    # 课程内部 md 链接 → html
    html = re.sub(r'href="((?:\.\./)*(?!https?:)[^":]*?)\.md"',
                  lambda m: f'href="{m.group(1)}.html"', html)
    # learn-pi 的 README 在站上是 hub（index.html）；practice 工作区入口是 index.html
    html = re.sub(r'href="((?:\.\./)*)learn-pi/README\.html"',
                  lambda m: f'href="{m.group(1)}learn-pi/index.html"', html)
    html = re.sub(r'href="((?:\./)*)practice/README\.html"',
                  lambda m: f'href="{m.group(1)}practice/index.html"', html)
    return html


def quote_nonascii_html(html):
    """href 里的非 ASCII 路径百分号编码（站点链接一贯形态）"""
    def _q(m):
        path = m.group(1)
        if re.search(r"[^\x21-\x7e]", path):
            return f'href="{url_quote(path, safe="/.#")}"'
        return m.group(0)
    return re.sub(r'href="([^"]+)"', _q, html)


# ---------------------------------------------------------------- 课程页外壳

def md_render(text):
    html = markdown.markdown(text, extensions=MD_EXTS, output_format="html5")
    # 与现有页面的紧凑表格形态一致（markdown 3.11 默认在 tbody 后折行）
    html = html.replace("<tbody>\n<tr>", "<tbody><tr>").replace("</tbody>\n</table>", "</tbody></table>")
    # 任务列表：markdown 核心不支持，按 GitHub 形态补渲染
    html = html.replace("<li>[ ] ", '<li><input disabled="" type="checkbox"> ')
    html = html.replace("<li>[x] ", '<li><input disabled="" type="checkbox" checked=""> ')
    return html


def page_title(md_text, fallback):
    m = re.search(r"^# (.+)$", md_text, re.M)
    return m.group(1).strip() if m else fallback


def shell_page(*, body, title, desc, depth, crumbs_href, crumbs_label,
               footer_zone, pager="", zone_dir="learn-pi", crumbs_html=None,
               footer_extra=True):
    P = "../" * depth
    if crumbs_html is None:
        crumbs_html = (f'<nav class="crumbs"><a href="{P}{crumbs_href}">{crumbs_label}</a></nav>'
                       if crumbs_href else '<nav class="crumbs"></nav>')
    sister = (f' · 姊妹课程 <a href="{P}agent-harness-course/index.html">Agent Harness 架构课</a>'
              if footer_extra else "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="{P}{zone_dir}/style.css">
{THEME_PREFILL}
</head>
<body>
<div class="wrap">
  {crumbs_html}
  <article>
{body}

  </article>
{pager}  <footer>{footer_zone} · 基准 pi 1.0.2（2026-10-04） · <a href="https://github.com/NorthAdb/pi-agent-north" target="_blank" rel="noopener">源码仓库 ↗</a>{sister}</footer>
</div>
{THEME_TOGGLE}
</body>
</html>
"""


def rel_href(url, cur_dir):
    """learn-pi 根相对 url → 从 cur_dir（learn-pi 根相对目录，'' 为根）出发的相对链接（不做百分号编码）"""
    return posixpath.relpath(url, cur_dir or ".")


def pager_nav(prev, next_, cur_dir):
    """prev/next: (标题, learn-pi 根相对 url) or None；输出与现有页面逐字节一致的三种形态"""
    if prev and next_:
        return (f'<nav class="pager"><a href="{rel_href(prev[1], cur_dir)}">← {prev[0]}</a>\n'
                f'    <span class="spacer"></span>\n'
                f'    <a href="{rel_href(next_[1], cur_dir)}">{next_[0]} →</a></nav>\n')
    if next_:
        return (f'<nav class="pager"><span class="spacer"></span>\n'
                f'    <a href="{rel_href(next_[1], cur_dir)}">{next_[0]} →</a></nav>\n')
    if prev:
        return (f'<nav class="pager"><a href="{rel_href(prev[1], cur_dir)}">← {prev[0]}</a>\n'
                f'    <span class="spacer"></span></nav>\n')
    return ""


# ---------------------------------------------------------------- learn-pi

def build_learn_pi():
    src = PI / "learn-pi"
    zone = SITE / "learn-pi"
    # style.css 是站点自有资产：清空目录时保留，不参与重建
    for child in zone.iterdir():
        if child.name == "style.css":
            continue
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    zone.mkdir(parents=True, exist_ok=True)

    readme = (src / "README.md").read_text(encoding="utf-8")
    # 阅读顺序 = README 课表里的 md 链接次序；表外文件按路径排序追加
    order = re.findall(r"\]\(((?:\d\d-[^/)]+/)?[^/)]+\.md)\)", readme)
    order = [p for p in order if not p.startswith("README")]
    all_md = sorted((p.relative_to(src).as_posix() for p in src.rglob("*.md")
                     if p.name != "README.md"), key=lambda s: s)
    seq = order + [p for p in all_md if p not in order]

    titles = {}
    for rel in seq:
        titles[rel] = page_title((src / rel).read_text(encoding="utf-8"),
                                 Path(rel).stem)

    # hub = README 渲染
    hub_title = page_title(readme, "学习 Pi Agent（learn-pi）")
    body = md_render(readme)
    body = rewrite_links(body)
    body = quote_nonascii_html(body)
    html = shell_page(body=body, title=f"{hub_title} · 学习 Pi 导读",
                      desc=f"{hub_title} · 学习 Pi 导读 — NorthAdb 课件",
                      depth=1, crumbs_href="", crumbs_label="",
                      footer_zone="学习 Pi 导读（learn-pi）")
    (zone / "index.html").write_text(html, encoding="utf-8", newline="\n")

    for i, rel in enumerate(seq):
        out_rel = Path(rel).with_suffix(".html")
        depth = len(out_rel.parts)
        P = "../" * depth
        prev = (titles[seq[i - 1]], posixpath.splitext(seq[i - 1])[0] + ".html") if i else None
        nxt = (titles[seq[i + 1]], posixpath.splitext(seq[i + 1])[0] + ".html") \
            if i + 1 < len(seq) else None
        body = md_render((src / rel).read_text(encoding="utf-8"))
        body = rewrite_links(body)
        body = quote_nonascii_html(body)
        pager = pager_nav(prev, nxt, str(out_rel.parent))
        html = shell_page(body=body, title=f"{titles[rel]} · 学习 Pi 导读",
                          desc=f"{titles[rel]} · 学习 Pi 导读 — NorthAdb 课件",
                          depth=depth, crumbs_href="learn-pi/index.html",
                          crumbs_label="← 总目录",
                          footer_zone="学习 Pi 导读（learn-pi）", pager=pager)
        out = zone / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8", newline="\n")

    # sitemap 顺序与历史一致：index 在前，其余按路径排序（与阅读顺序无关）
    return (["learn-pi/index.html"]
            + sorted(f"learn-pi/{posixpath.splitext(r)[0]}.html" for r in seq))


# ---------------------------------------------------------------- agent-harness-course

COURSE_CSS_DARK = '''
/* 手动暗色（主题切换按钮） */
[data-theme="dark"] {
  --ink: #e8e4da; --ink-soft: #b3aea2; --paper: #1c1b18;
  --accent: #5cc8b4; --accent-soft: #1d332e; --warn: #d9a35a; --warn-soft: #3a2d18;
  --fact: #7db3e8; --fact-soft: #1b2a3a; --guess: #a996d9; --guess-soft: #2a2440;
  --line: #3a362e; --code-bg: #26231d;
}
[data-theme="dark"] .quiz { background: #232019; }
[data-theme="dark"] a { color: var(--accent); }
'''


WF_CSS_DARK = """
/* 手动暗色（主题切换按钮）—— 与博客设计令牌一致的暗色组 */
[data-theme="dark"] {
  --ink: #e4e4e7;
  --muted: #a1a1aa;
  --accent: #5eead4;
  --accent-soft: rgba(94, 234, 212, 0.12);
  --bg: #0a0a0a;
  --panel: #16161a;
  --line: #27272a;
  --code-bg: #101013;
  --code-ink: #d6d6e0;
}
[data-theme="dark"] .quiz { background: #101013; }
[data-theme="dark"] .quiz button { background: #16161a; }
[data-theme="dark"] .quiz button.wrong { background: rgba(248, 113, 113, 0.15); }
[data-theme="dark"] th { background: #16161a; }
"""


def patch_course_css(text):
    text = text.replace("  :root {", '  :root:not([data-theme="light"]) {')
    text = text.replace("  .quiz { background: #232019; }",
                        '  :root:not([data-theme="light"]) .quiz { background: #232019; }')
    text = text.replace("  a { color: var(--accent); }",
                        '  :root:not([data-theme="light"]) a { color: var(--accent); }')
    return text.rstrip("\n") + "\n" + COURSE_CSS_DARK


def build_harness():
    src = PI / "agent-harness-course"
    zone = SITE / "agent-harness-course"
    if zone.exists():
        shutil.rmtree(zone)

    skip_parts = {"learning-records", "__pycache__", ".git"}
    urls = ["agent-harness-course/index.html", "agent-harness-course/COURSE.html",
            "agent-harness-course/diagrams.html", "agent-harness-course/practice/index.html"]

    for p in sorted(src.rglob("*"), key=lambda x: x.parts):
        rel = p.relative_to(src)
        if skip_parts & set(rel.parts) or ".visual-check." in p.name:
            continue  # visual-check.* 与 qa.py 是仓库里的 QA 产物，不发布
        if p.name == "qa.py":
            continue
        out = zone / rel
        if p.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.name in ("COURSE.md", "NOTES.md"):
            continue  # 不发布：COURSE.html 由 COURSE.md 渲染，NOTES.md 是仓库内部笔记
        if p.suffix == ".css" and p.name == "course.css":
            out.write_text(patch_course_css(p.read_text(encoding="utf-8")),
                           encoding="utf-8", newline="\n")
            continue
        if p.suffix == ".html":
            text = p.read_text(encoding="utf-8")
            text = rewrite_links(text)
            injected = theme_inject(text)
            if injected is not None:
                text = injected
            out.write_text(text, encoding="utf-8", newline="\n")
            continue
        shutil.copyfile(p, out)  # js/json/png 等按字节拷贝

    # COURSE.md / practice/README.md 渲染成站点外壳页
    for md_rel, out_rel, h1_suffix, footer, crumbs in [
            ("COURSE.md", "COURSE.html", "Agent Harness 架构课程",
             "Agent Harness 架构课程", None),
            ("practice/README.md", "practice/index.html", "Agent Harness 架构课程",
             "毕业练习工作区",
             ('<nav class="crumbs"><a href="../../agent-harness-course/index.html">课程首页</a>'
              ' <span>·</span> <a href="../../agent-harness-course/COURSE.html">总纲</a></nav>'))]:
        md_text = (src / md_rel).read_text(encoding="utf-8")
        h1 = page_title(md_text, Path(md_rel).stem)
        depth = len(Path(out_rel).parts)
        body = md_render(md_text)
        body = rewrite_links(body)
        body = quote_nonascii_html(body)
        html = shell_page(body=body, title=f"{h1} · {h1_suffix}",
                          desc=f"{h1} · {h1_suffix} — NorthAdb 课件",
                          depth=depth, crumbs_href="agent-harness-course/index.html",
                          crumbs_label="← 课程首页",
                          footer_zone=footer, zone_dir="learn-pi", crumbs_html=crumbs)
        (zone / out_rel).write_text(html, encoding="utf-8", newline="\n")

    urls += [f"agent-harness-course/{p.relative_to(zone).as_posix()}"
             for p in sorted(zone.glob("lessons/*.html"))]
    urls += [f"agent-harness-course/{p.relative_to(zone).as_posix()}"
             for p in sorted(zone.glob("reference/*.html"))]
    return urls


# ---------------------------------------------------------------- web-foundation

WF_INDEX_REDIRECT = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url=COURSE.html">
<link rel="canonical" href="./COURSE.html">
<title>从 HTTP 到实时 Agent Server</title>
</head>
<body>
<p>正在进入课程首页…… <a href="COURSE.html">如果没有自动跳转，点这里</a>。</p>
</body>
</html>
"""


def build_web_foundation():
    subprocess.run([sys.executable, "tools/build_docs.py"], cwd=WF, check=True,
                   stdout=subprocess.DEVNULL)
    src = WF
    zone = SITE / "web-foundation"
    if zone.exists():
        shutil.rmtree(zone)

    skip_parts = {".git", "__pycache__", "learning-records"}
    for p in sorted(src.rglob("*"), key=lambda x: x.parts):
        rel = p.relative_to(src)
        if skip_parts & set(rel.parts) or rel.parts[0] == ".git":
            continue
        if p.name == "NOTES.md":
            continue
        out = zone / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.is_dir():
            continue
        text = p.read_text(encoding="utf-8")
        if p.suffix == ".html" and rel.as_posix() != "index.html":
            injected = theme_inject(text)
            if injected is not None:
                text = injected
        elif p.suffix != ".html":
            if rel.as_posix() == "assets/course.css":
                out.write_text(text.rstrip("\n") + "\n" + WF_CSS_DARK,
                               encoding="utf-8", newline="\n")
                continue
            shutil.copyfile(p, out)  # md/py/json/png 等按字节拷贝
            continue
        out.write_text(text, encoding="utf-8", newline="\n")

    (zone / "index.html").write_text(WF_INDEX_REDIRECT, encoding="utf-8", newline="\n")

    urls = ["web-foundation/index.html"]
    urls += sorted(f"web-foundation/{p.relative_to(zone).as_posix()}"
                   for p in zone.glob("*.html")
                   if p.name not in ("index.html",) and not p.name.startswith("SSE_"))
    for sub in ("course", "lessons", "reference", "diagrams"):
        urls += sorted(f"web-foundation/{p.relative_to(zone).as_posix()}"
                       for p in zone.glob(f"{sub}/*.html"))
    return urls


# ---------------------------------------------------------------- search / sitemap

SEARCH_ENTRIES = [
    {"title": "Agent Harness 架构课程", "url": "agent-harness-course/index.html",
     "category": "课件 · 15 课",
     "excerpt": "逆向工程 Pi 源码，回答现代 Agent Harness 需要哪些基础机制。",
     "type": "course", "featured": False,
     "keywords": "agent harness pi loop tool context session compaction skills mcp"},
    {"title": "学习 Pi 导读", "url": "learn-pi/index.html", "category": "课件 · 22 篇",
     "excerpt": "面向 Pi 仓库的中文学习导读：设计哲学、架构、运行模式与二次开发。",
     "type": "course", "featured": False, "keywords": "pi agent 导读 架构 设计哲学"},
    {"title": "从 HTTP 到实时 Agent Server", "url": "web-foundation/COURSE.html",
     "category": "课件 · 网络通信课",
     "excerpt": "异步与 HTTP 地基、SSE 流式、WebSocket 双向通信，到 Agent 事件流与生产化。",
     "type": "course", "featured": False,
     "keywords": "http sse websocket fastapi redis nginx agent server 网络"},
    {"title": "Web & Infra", "url": "web-foundation/COURSE.html", "category": "方向",
     "excerpt": "从 HTTP 到 Redis / Nginx 生产化的网络通信课。",
     "type": "topic", "featured": False},
]

ZONES = ("agent-harness-course", "learn-pi", "web-foundation")


def update_search():
    path = SITE / "search.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    items = [i for i in items if str(i.get("url", "")).split("/")[0] not in ZONES]
    items.extend(SEARCH_ENTRIES)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def update_sitemap(zone_urls):
    path = SITE / "sitemap.xml"
    text = path.read_text(encoding="utf-8")
    # 每个区块原地重建：用占位符记住本区第一个 <url> 的位置，其余剥掉
    for z in ZONES:
        pat = (rf"  <url>\n    <loc>{SITE_URL}/{z}/[^<]*</loc>\n    <lastmod>[^<]*</lastmod>\n"
               rf"(?:    <priority>[^<]*</priority>\n)?  </url>\n")
        first = {"done": False}

        def _stash(m):
            if not first["done"]:
                first["done"] = True
                return f"<!--ZONE:{z}-->"
            return ""

        text = re.sub(pat, _stash, text)
    text = re.sub(r"  <url>\n    <lastmod>[^<]*</lastmod>\n  </url>\n", "", text)
    for z in ZONES:
        block = "".join(
            f"  <url>\n    <loc>{SITE_URL}/{u}</loc>\n    <lastmod>{TODAY}</lastmod>\n"
            f"    <priority>0.6</priority>\n  </url>\n" for u in zone_urls[z])
        text = text.replace(f"<!--ZONE:{z}-->", block)
    path.write_text(text, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- main

def main():
    for repo in (PI, WF):
        if not repo.exists():
            sys.exit(f"missing source repo: {repo} — 先 clone（pi-agent-north 需 checkout course 分支）")

    urls = {}
    urls["learn-pi"] = build_learn_pi()
    urls["agent-harness-course"] = build_harness()
    urls["web-foundation"] = build_web_foundation()
    update_search()
    update_sitemap(urls)
    print(f"learn-pi: {len(urls['learn-pi'])} pages · "
          f"harness: {len(urls['agent-harness-course'])} · "
          f"web-foundation: {len(urls['web-foundation'])}")


if __name__ == "__main__":
    main()
