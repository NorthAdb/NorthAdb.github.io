"""三个课程区块的同步构建（渲染进站点设计系统），源仓库即唯一事实来源：

- agent-harness-course/  ← pi-agent-north@course：hub 重排为站点 hero + 课程卡片；
                           课件/参考页内容（预渲染 HTML）抽取进站点外壳；图页保持独立 iframe
- learn-pi/              ← 同分支 learn-pi/*.md：渲染成站点文章页（post-hero + prose + 翻页）
- web-foundation/        ← web_fundation：先跑仓库自带 tools/build_docs.py，内容抽取进站点外壳

外壳与站点其他区块完全一致（导航/搜索/页脚/设计令牌），课件特有组件
（证据徽章、callout、测验、架构图容器）由 assets/courses.css overlay 提供。
CI（deploy.yml）先 clone 源仓库再运行本脚本；输出确定性（LF、排序遍历）。
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

import build_notes as site_tmpl   # 复用站点外壳：导航/页脚/搜索/收藏夹图标

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
PI_REPO = "https://github.com/NorthAdb/pi-agent-north"
PI_BLOB = f"{PI_REPO}/blob/main"
PI_TREE_COURSE = f"{PI_REPO}/tree/course"
TODAY = "2026-10-07"

MD_EXTS = ["extra", "sane_lists"]


def strip_h1(md_text):
    """剥掉首个 H1：标题已由 post-hero 呈现，避免重复"""
    return re.sub(r"^# [^\n]+\n+", "", md_text, count=1)


def md_render(text):
    html = markdown.markdown(text, extensions=MD_EXTS, output_format="html5")
    # 与站点已渲染页面的紧凑表格形态一致（markdown 3.11 默认在 tbody 后折行）
    html = html.replace("<tbody>\n<tr>", "<tbody><tr>").replace("</tbody>\n</table>", "</tbody></table>")
    # 任务列表：markdown 核心不支持，按 GitHub 形态补渲染
    html = html.replace("<li>[ ] ", '<li><input disabled="" type="checkbox"> ')
    html = html.replace("<li>[x] ", '<li><input disabled="" type="checkbox" checked=""> ')
    return html


# ---------------------------------------------------------------- 站点外壳

def site_shell(P, title, desc, canonical, body, overlay=None):
    ov = f'\n<link rel="stylesheet" href="{P}{overlay}">' if overlay else ""
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{SITE_URL}/{canonical}">
<meta name="theme-color" content="#0a0a0a">
<meta property="og:type" content="article">
<meta property="og:site_name" content="NorthAdb">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{SITE_URL}/{canonical}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
{site_tmpl.FAVICON}
<link rel="alternate" type="application/rss+xml" title="NorthAdb 的博客" href="{P}feed.xml">
<link rel="stylesheet" href="{P}css/style.css">{ov}
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.setAttribute("data-theme",t);}}catch(e){{}}</script>
</head>
<body data-root="{P}" data-page="post">

<div class="progress" id="progress"></div>

{site_tmpl.nav_html(P)}

<main>
{body}
</main>

{site_tmpl.footer_html(P)}

{site_tmpl.CMDK}

<button class="to-top" id="toTop" aria-label="回到顶部">↑</button>

<script src="{P}js/main.js" defer></script>
</body>
</html>'''


def crumb(P, *pairs):
    parts = [f'<a href="{P}index.html">首页</a>']
    for href, label in pairs:
        parts.append('<span>/</span>')
        parts.append(f'<a href="{P}{href}">{label}</a>' if href else f'<span>{label}</span>')
    return '<div class="crumbs">' + "".join(parts) + "</div>"


TOC_BLOCKS = '''<div class="toc-mobile">
          <details>
            <summary>On this page</summary>
            <nav class="toc"><div class="toc-build"></div></nav>
          </details>
        </div>'''


def doc_page(P, *, title, desc, canonical, prose, overlay, hero="", foot="",
             post_nav="", toc=True):
    """文章型页面：post-hero（可选）+ prose + 桌面目录 aside + post-foot（可选）"""
    toc_mob = TOC_BLOCKS if toc else ""
    aside = ('''<aside>
      <nav class="toc">
        <div class="toc-title">On this page</div>
        <div class="toc-build"></div>
      </nav>
    </aside>''' if toc else "")
    body = f'''  <div class="post-layout">
    <div class="post-main">
      <article>
        {hero}{toc_mob}
        <div class="prose course-doc">
{prose}
        </div>
        {foot}
      </article>
    </div>
    {aside}
  </div>

  {post_nav}'''
    return site_shell(P, title, desc, canonical, body, overlay=overlay)


def post_nav(prev, next_):
    """站点样式的上一篇/下一篇；prev/next: (标题, 链接) or None"""
    if not prev and not next_:
        return ""
    prev_a = '<span></span>'
    if prev:
        prev_a = (f'<a class="prev" href="{prev[1]}"><span class="dir">← 上一篇</span>'
                  f'<span class="t">{prev[0]}</span></a>')
    next_a = ""
    if next_:
        next_a = (f'<a class="next" href="{next_[1]}"><span class="dir">下一篇 →</span>'
                  f'<span class="t">{next_[0]}</span></a>')
    return f'<div class="wrap"><nav class="post-nav">{prev_a}{next_a}</nav></div>\n'


def hero(kicker, h1, sub, actions, stats):
    acts = "".join(f'\n      {a}' for a in actions)
    sts = "".join(f'\n      <div>{s}</div>' for s in stats)
    return f'''<section class="hero wrap">
    <div class="hero-glow"></div>
    <div class="hero-kicker"><span class="dot"></span> {kicker}</div>
    <h1>{h1}</h1>
    <p class="sub">{sub}</p>
    <div class="hero-actions">{acts}
    </div>
    <div class="hero-stats">{sts}
    </div>
  </section>'''


# ---------------------------------------------------------------- 链接改写

REPO_SRC = r"(?:packages|scripts|docs|examples|nix)"


def rewrite_links(html):
    """pi-agent-north 课程内容的链接改写（md 渲染产物与拷贝的 html 通用）"""
    def blob_or_tree(m):
        # 有扩展名的路径指文件（blob），无扩展名指目录（tree）
        kind = "tree" if not Path(m.group(2)).suffix else "blob"
        return f'href="{PI_REPO}/{kind}/main/{m.group(2)}"'
    # learning-records 不发布：整条入口先移除（在链接改写之前，避免 href 被先行替换）
    html = re.sub(r'\s*<a class="pill" href="learning-records/README\.md">[^<]*</a>', "", html)
    # 仓库源码/文档相对链接 → GitHub blob/tree（learn-pi/、agent-harness-course/ 是站内内容，除外）
    html = re.sub(rf'href="((?:\.\./)+)({REPO_SRC}/[^"]+)"', blob_or_tree, html)
    html = re.sub(rf'href="((?:\.\./)+)((?:README|AGENTS|CONTRIBUTING|SECURITY)\.md)"',
                  rf'href="{PI_BLOB}/\2"', html)
    # learning-records 只存在于 course 分支且不在站点发布，指回 GitHub（README 归一化为目录）
    lr = f"{PI_TREE_COURSE}/agent-harness-course/learning-records"
    html = re.sub(r'href="((?:\.\./)*)learning-records/README\.(?:md|html)"', f'href="{lr}"', html)
    html = re.sub(r'href="((?:\.\./)*)learning-records/([^"]+)"', rf'href="{lr}/\2"', html)
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
    """href 里的非 ASCII 路径百分号编码（markdown 渲染产物用）"""

    def _q(m):
        path = m.group(1)
        if re.search(r"[^\x21-\x7e]", path):
            return f'href="{url_quote(path, safe="/.#")}"'
        return m.group(0)

    return re.sub(r'href="([^"]+)"', _q, html)


def extract_content(html):
    """从仓库预渲染页面中取正文：去旧主题按钮/脚本、build_docs 页脚与侧栏脚本"""
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    body = m.group(1) if m else html
    body = re.sub(r'<button id="themeToggle".*?</button>\s*', "", body, flags=re.S)
    body = re.sub(r'<script>\(function\(\)\{var b=document\.getElementById\("themeToggle"\).*?</script>\s*',
                  "", body, flags=re.S)
    body = re.sub(r'<footer>本页由 markdown 源文件.*?</footer>\s*', "", body, flags=re.S)
    body = re.sub(r'<script src="assets/nav\.js"[^>]*></script>\s*', "", body, flags=re.S)
    return body.strip("\n")


# ---------------------------------------------------------------- overlay css

COURSES_CSS = """/* ============================================================
   三课程区 overlay —— 建立在站点设计令牌（css/style.css）之上。
   承接源仓库课件里的既有组件：证据徽章 / callout / 测验 / 架构图容器。
   ============================================================ */

.course-doc .kicker {
  font-family: var(--font-mono, ui-monospace, Consolas, monospace);
  font-size: .78rem; letter-spacing: .12em; text-transform: uppercase;
  color: var(--accent); margin: .2rem 0 .6rem;
}
.course-doc .lede { font-size: 1.05rem; color: var(--text-2); margin-top: .6rem; }
.course-doc .question {
  border-left: 3px solid var(--accent);
  background: var(--accent-soft);
  padding: .9rem 1.2rem;
  border-radius: 0 8px 8px 0;
  margin: 1.6rem 0;
  font-size: 1.02rem;
}
.course-doc .question strong { color: var(--accent-strong); }

/* 证据徽章 */
.course-doc .badge {
  display: inline-block;
  font-family: var(--font-mono, ui-monospace, Consolas, monospace);
  font-size: .72rem;
  padding: .1em .55em;
  border-radius: 99px;
  vertical-align: middle;
  margin-right: .35em;
}
.course-doc .badge.src { background: rgba(96, 165, 250, .12); color: #7db3e8; }
.course-doc .badge.doc { background: var(--accent-soft); color: var(--accent-strong); }
.course-doc .badge.guess { background: rgba(167, 139, 250, .13); color: #b9a5e8; }
.course-doc .badge.generic { background: rgba(217, 163, 90, .13); color: #d9a35a; }

.course-doc .callout { border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.3rem; margin: 1.4rem 0; }
.course-doc .callout.fact { border-left: 3px solid #7db3e8; }
.course-doc .callout.doc { border-left: 3px solid var(--accent); }
.course-doc .callout.guess { border-left: 3px solid #b9a5e8; }
.course-doc .callout.generic { border-left: 3px solid #d9a35a; }
.course-doc .callout .t { font-weight: bold; font-size: .85rem; letter-spacing: .06em; display: block; margin-bottom: .3rem; color: var(--text-2); }

/* 源码映射表 */
.course-doc table.map { font-size: .92rem; }
.course-doc table.map th { font-family: var(--font-mono, ui-monospace, Consolas, monospace); font-size: .8rem; }
.course-doc table.map td code { white-space: nowrap; }

/* 七问 */
.course-doc .seven { counter-reset: q; margin: 1rem 0; padding: 0; list-style: none; }
.course-doc .seven li { counter-increment: q; margin: .7rem 0; padding-left: 2.2rem; position: relative; }
.course-doc .seven li::before {
  content: counter(q);
  position: absolute; left: 0; top: .15em;
  width: 1.5rem; height: 1.5rem;
  background: var(--accent); color: #fff;
  border-radius: 50%;
  font-family: var(--font-mono, ui-monospace, Consolas, monospace); font-size: .8rem;
  display: flex; align-items: center; justify-content: center;
}
.course-doc .seven li b { color: var(--accent-strong); }

/* 测验 */
.course-doc .quiz { border: 1px solid var(--border); border-radius: 10px; padding: 1.2rem 1.4rem; margin: 2rem 0; background: var(--bg-1); }
.course-doc .quiz h3 { margin-top: 0; }
.course-doc .quiz fieldset { border: none; margin: 1.2rem 0 0; padding: 0; }
.course-doc .quiz legend { font-weight: bold; margin-bottom: .4rem; }
.course-doc .quiz label { display: block; margin: .35rem 0; cursor: pointer; font-size: .95rem; }
.course-doc .quiz .btn {
  margin-top: 1rem;
  background: var(--accent); color: #fff;
  border: none; border-radius: 6px;
  padding: .5rem 1.3rem; font-size: .95rem; cursor: pointer;
  font-family: inherit;
}
.course-doc .quiz .btn:hover { filter: brightness(1.08); }
.course-doc .quiz .result { margin-top: .8rem; font-size: .95rem; min-height: 1.4em; }
.course-doc .quiz .ok { color: var(--accent-strong); font-weight: bold; }
.course-doc .quiz .bad { color: #f87171; font-weight: bold; }
.course-doc .quiz .why { font-size: .88rem; color: var(--text-2); margin-top: .5rem; }

/* 架构图容器（iframe 嵌入 lessons/diagrams/*.html） */
.course-doc figure.diagram { margin: 2rem 0; }
.course-doc figure.diagram iframe {
  width: 100%;
  height: 820px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: #fff;
}
.course-doc figure.diagram figcaption { font-size: .85rem; color: var(--text-3); margin-top: .5rem; }

/* 课件内的课间翻页与脚注（源仓库自带结构） */
.course-doc nav.pager { display: flex; justify-content: space-between; gap: 1rem; margin-top: 3rem;
  font-family: var(--font-mono, ui-monospace, Consolas, monospace); font-size: .88rem; }
.course-doc nav.pager a { color: var(--accent-strong); text-decoration: none; }
.course-doc nav.pager a:hover { text-decoration: underline; }
.course-doc footer.note { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border);
  font-size: .85rem; color: var(--text-3); }
"""


def write_overlay(zone_dir):
    (zone_dir / "assets").mkdir(parents=True, exist_ok=True)
    (zone_dir / "assets" / "courses.css").write_text(COURSES_CSS, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- learn-pi

def build_learn_pi():
    src = PI / "learn-pi"
    zone = SITE / "learn-pi"
    if zone.exists():
        shutil.rmtree(zone)

    readme = (src / "README.md").read_text(encoding="utf-8")
    # 阅读顺序 = README 课表里的 md 链接次序；表外文件按路径排序追加
    order = [p for p in re.findall(r"\]\(((?:\d\d-[^/)]+/)?[^/)]+\.md)\)", readme)
             if not p.startswith("README")]
    all_md = sorted(p.relative_to(src).as_posix() for p in src.rglob("*.md")
                    if p.name != "README.md")
    seq = order + [p for p in all_md if p not in order]

    titles, goals, stages = {}, {}, {}
    for row in re.findall(r"^\|\s*([^|]+)\|\s*\[[^\]]+\]\(([^)]+\.md)\)\s*\|\s*([^|]+)\|",
                          readme, re.M):
        goals[row[1].strip()] = row[2].strip()
        stages[row[1].strip()] = row[0].strip()
    for rel in seq:
        m = re.search(r"^# (.+)$", (src / rel).read_text(encoding="utf-8"), re.M)
        titles[rel] = m.group(1).strip() if m else Path(rel).stem

    overlay = "learn-pi/assets/courses.css"
    write_overlay(zone)

    def gh_src(rel):
        return f"{PI_TREE_COURSE}/learn-pi/{url_quote(rel, safe='/')}"

    # ---- hub：站点 hero + 各阶段卡片 ----
    stage_order, groups = [], {}
    for rel in seq:
        st = stages.get(rel, "进阶")
        if st not in groups:
            groups[st] = []
            stage_order.append(st)
        groups[st].append(rel)
    secs = []
    for st in stage_order:
        cards = "".join(
            f'''\n        <a class="course-card" href="{url_quote(posixpath.splitext(r)[0] + '.html', safe='/.#')}">
          <span class="c-badge">{posixpath.splitext(r)[0].split("/")[0]}</span>
          <h3>{titles[r]}</h3>
          <p>{goals.get(r, "")}</p>
          <span class="c-link">阅读 →</span>
        </a>''' for r in groups[st])
        secs.append(f'''  <section class="block wrap">
    <div class="sec-head reveal"><span class="label">{st}</span></div>
    <div class="course-grid reveal">{cards}
    </div>
  </section>''')
    first_href = url_quote(posixpath.splitext(seq[0])[0] + ".html", safe="/.#")
    hub_body = hero(
        "Course · Learning Pi — fork of earendil-works/pi",
        '学习 <em>Pi</em> 导读',
        ('面向 Pi 仓库的中文学习导读：设计哲学、架构、运行模式与二次开发，处处指向源码与官方文档。'
         f'<span class="dim">整理自 <a href="{PI_TREE_COURSE}/learn-pi" target="_blank" rel="noopener">NorthAdb/pi-agent-north</a> 的 learn-pi/，22 篇在线可读。</span>'),
        [f'<a href="{first_href}" class="btn btn-primary">从「什么是 Pi」开始</a>',
         f'<a href="{PI_TREE_COURSE}/learn-pi" class="btn btn-ghost" target="_blank" rel="noopener">源仓库 ↗</a>',
         f'<a href="{url_quote("07-参考/术语表.html", safe="/.#")}" class="btn btn-ghost">术语表</a>'],
        ['<b data-count="22">22</b>篇导读',
         '<b data-count="8">8</b>个阶段',
         '<b data-count="20" data-suffix="+">20+</b>关键文件清单',
         '<b>1.0.2</b>基准版本']) + "\n" + "\n".join(secs)
    (zone / "index.html").write_text(
        site_shell("../", "学习 Pi 导读 — NorthAdb 的博客",
                   "面向 Pi 仓库的中文学习导读：设计哲学、架构、运行模式与二次开发。",
                   "learn-pi/index.html", hub_body, overlay=overlay),
        encoding="utf-8", newline="\n")

    # ---- 文章页 ----
    for i, rel in enumerate(seq):
        out_rel = posixpath.splitext(rel)[0] + ".html"
        depth = out_rel.count("/") + 1
        P = "../" * depth
        md_text = (src / rel).read_text(encoding="utf-8")
        body_html = rewrite_links(quote_nonascii_html(md_render(strip_h1(md_text))))
        prev = next_ = None
        if i:
            pr = posixpath.splitext(seq[i - 1])[0] + ".html"
            prev = (titles[seq[i - 1]], url_quote(pr, safe="/.#"))
        if i + 1 < len(seq):
            nx = posixpath.splitext(seq[i + 1])[0] + ".html"
            next_ = (titles[seq[i + 1]], url_quote(nx, safe="/.#"))
        minutes = max(1, len(md_text) // 400)
        stage = stages.get(rel, "")
        hero_html = f'''<header class="post-hero">
          {crumb(P, ("learn-pi/index.html", "学习 Pi 导读"))}
          <h1>{titles[rel]}</h1>
          <p class="post-sub">{goals.get(rel, "")}</p>
          <div class="post-meta">
            <span class="avatar">N</span>
            <span>学习 Pi 导读</span><span class="sep"></span>
            <span>阅读约 {minutes} 分钟</span>
          </div>
        </header>'''
        foot = f'''<footer class="post-foot">
          <div class="tags"><span class="chip chip-accent">学习 Pi 导读</span><span class="chip">{stage}</span></div>
          <a class="t-meta" href="{gh_src(rel)}" target="_blank" rel="noopener">在 GitHub 查看原文 ↗</a>
        </footer>'''
        html = doc_page(P, title=f"{titles[rel]} · 学习 Pi 导读 — NorthAdb 的博客",
                        desc=goals.get(rel) or f"{titles[rel]} · 学习 Pi 导读",
                        canonical=f"learn-pi/{out_rel}", prose=body_html,
                        overlay=overlay, hero=hero_html, foot=foot,
                        post_nav=post_nav(prev, next_))
        out = zone / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8", newline="\n")

    return ["learn-pi/index.html"] + sorted(f"learn-pi/{r}" for r in
                                            (posixpath.splitext(x)[0] + ".html" for x in seq))


# ---------------------------------------------------------------- agent-harness-course

def build_harness():
    src = PI / "agent-harness-course"
    zone = SITE / "agent-harness-course"
    if zone.exists():
        shutil.rmtree(zone)
    write_overlay(zone)
    overlay = "agent-harness-course/assets/courses.css"

    skip = {"learning-records", "__pycache__", ".git"}
    urls = ["agent-harness-course/index.html", "agent-harness-course/COURSE.html",
            "agent-harness-course/diagrams.html", "agent-harness-course/practice/index.html"]

    # ---- 非 HTML 资产：字节拷贝（QA 产物除外）；HTML：内容抽取进站点外壳 ----
    for p in sorted(src.rglob("*"), key=lambda x: x.parts):
        rel = p.relative_to(src)
        if skip & set(rel.parts) or ".visual-check." in p.name or p.name == "qa.py":
            continue
        out = zone / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.is_dir():
            continue
        if p.suffix != ".html":
            shutil.copyfile(p, out)   # css/js/json/md/png 按字节拷贝（含 quiz.js、架构图 specs）
            continue
        rel_posix = rel.as_posix()
        if rel_posix.startswith("lessons/diagrams/"):
            # iframe 目标页：自包含样式，保持独立（保留历史主题按钮）
            text = p.read_text(encoding="utf-8")
            injected = re.sub(r"</head>", '<script>try{var t=localStorage.getItem("theme");'
                              'if(t)document.documentElement.setAttribute("data-theme",t);}catch(e){}</script>\n</head>',
                              text, count=1)
            out.write_text(injected, encoding="utf-8", newline="\n")
            continue

        content = rewrite_links(extract_content(p.read_text(encoding="utf-8")))
        depth = rel_posix.count("/") + 1
        P = "../" * depth
        html = doc_page(P, title=f"{rel.stem} · Agent Harness 架构课程 — NorthAdb 的博客",
                        desc=f"{rel.stem} · Agent Harness 架构课程 — NorthAdb 课件",
                        canonical=f"agent-harness-course/{rel_posix}",
                        prose=content, overlay=overlay)
        out.write_text(html, encoding="utf-8", newline="\n")
        if rel_posix.startswith(("lessons/0", "reference/")):
            urls.append(f"agent-harness-course/{rel_posix}")

    # ---- COURSE.html / practice/index.html：markdown 渲染成站点文章页 ----
    for md_rel, out_rel, crumb_label in [
            ("COURSE.md", "COURSE.html", "总纲"),
            ("practice/README.md", "practice/index.html", "毕业练习")]:
        md_text = (src / md_rel).read_text(encoding="utf-8")
        m = re.search(r"^# (.+)$", md_text, re.M)
        h1 = m.group(1).strip() if m else Path(md_rel).stem
        depth = out_rel.count("/") + 1
        P = "../" * depth
        body_html = rewrite_links(quote_nonascii_html(md_render(strip_h1(md_text))))
        hero_html = f'''<header class="post-hero">
          {crumb(P, ("agent-harness-course/index.html", "Agent Harness 架构课程"), ("", crumb_label))}
          <h1>{h1}</h1>
          <div class="post-meta">
            <span class="avatar">N</span>
            <span>Agent Harness 架构课程</span><span class="sep"></span>
            <span><a href="{PI_TREE_COURSE}/agent-harness-course/{md_rel}" target="_blank" rel="noopener">在 GitHub 查看原文 ↗</a></span>
          </div>
        </header>'''
        html = doc_page(P, title=f"{h1} · Agent Harness 架构课程 — NorthAdb 的博客",
                        desc=f"{h1} · Agent Harness 架构课程 — NorthAdb 课件",
                        canonical=f"agent-harness-course/{out_rel}",
                        prose=body_html, overlay=overlay, hero=hero_html)
        (zone / out_rel).write_text(html, encoding="utf-8", newline="\n")

    # ---- hub：站点 hero + 从仓库 index 抽取的阶段/卡片 ----
    idx = (src / "index.html").read_text(encoding="utf-8")
    phases = []
    for h2, block in re.findall(r'<h2>([^<]+)</h2>\s*<div class="grid">(.*?)</div>\s*</div>', idx, re.S):
        cards = re.findall(r'<a class="card" href="([^"]+)">\s*<div class="no">([^<]*)</div>'
                           r'<div class="t">([^<]*)</div>\s*<div class="q">([^<]*)</div>', block)
        phases.append((h2, cards))
    secs = []
    for h2, cards in phases:
        cs = "".join(
            f'''\n        <a class="course-card" href="{href}">
          <span class="c-badge">{no.split("·")[0].strip()}</span>
          <h3>{t}</h3>
          <p>{q}</p>
          <span class="c-link">进入课程 →</span>
        </a>''' for href, no, t, q in cards)
        secs.append(f'''  <section class="block wrap">
    <div class="sec-head reveal"><span class="label">{h2}</span></div>
    <div class="course-grid reveal">{cs}
    </div>
  </section>''')
    hub_body = hero(
        "Course · Agent Harness — 以 Pi 源码为工程样本",
        '从「会用 Agent」到「能造 <em>Agent</em>」',
        ('14 课逆向工程 Pi（本仓库）的真实源码，回答一个问题：<b>一个现代 Agent Harness 为了让 LLM 稳定、持续、安全地完成复杂任务，'
         '到底需要哪些基础机制？</b>终点：不看任何宣传页，从空白目录手写一个 Minimal Harness。'
         f'<span class="dim">整理自 <a href="{PI_TREE_COURSE}/agent-harness-course" target="_blank" rel="noopener">NorthAdb/pi-agent-north</a> course 分支，15 课在线可读。</span>'),
        ['<a href="COURSE.html" class="btn btn-primary">从课程总纲开始</a>',
         f'<a href="{PI_TREE_COURSE}/agent-harness-course" class="btn btn-ghost" target="_blank" rel="noopener">源仓库 ↗</a>',
         '<a href="practice/index.html" class="btn btn-ghost">毕业练习 ↗</a>',
         '<a href="diagrams.html" class="btn btn-ghost">架构图集</a>'],
        ['<b data-count="15">15</b>课 · 每课 15–25 分钟',
         '<b data-count="13">13</b>张交互架构图',
         '<b data-count="17">17</b>个毕业练习验收测试',
         '<b data-count="30" data-suffix="+">30+</b>源码文件地图']) + "\n" + "\n".join(secs)
    (zone / "index.html").write_text(
        site_shell("../", "Agent Harness 架构课程 — NorthAdb 的博客",
                   "逆向工程 Pi 源码，回答现代 Agent Harness 需要哪些基础机制。",
                   "agent-harness-course/index.html", hub_body, overlay=overlay),
        encoding="utf-8", newline="\n")

    return urls


# ---------------------------------------------------------------- web-foundation

WF_DOC_PREFIXES = ("COURSE.html", "GLOSSARY.html", "MISSION.html", "README.html",
                   "RESOURCES.html", "SSE_", "course/", "lessons/", "reference/")


def build_web_foundation():
    subprocess.run([sys.executable, "tools/build_docs.py"], cwd=WF, check=True,
                   stdout=subprocess.DEVNULL)
    src = WF
    zone = SITE / "web-foundation"
    if zone.exists():
        shutil.rmtree(zone)
    write_overlay(zone)
    overlay = "web-foundation/assets/courses.css"

    skip = {".git", "__pycache__", "learning-records"}
    for p in sorted(src.rglob("*"), key=lambda x: x.parts):
        rel = p.relative_to(src)
        if skip & set(rel.parts) or p.name == "NOTES.md":
            continue
        out = zone / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.is_dir():
            continue
        rel_posix = rel.as_posix()
        if p.suffix == ".html" and rel_posix != "index.html" and (
                (rel_posix.startswith(WF_DOC_PREFIXES) and not Path(rel_posix).name.startswith("SSE_"))
                or re.match(r"labs/[^/]+/README\.html$", rel_posix)):
            content = extract_content(p.read_text(encoding="utf-8"))
            depth = rel_posix.count("/") + 1
            P = "../" * depth
            html = doc_page(P, title=f"{rel.stem} · 从 HTTP 到实时 Agent Server — NorthAdb 的博客",
                            desc=f"{rel.stem} · 从 HTTP 到实时 Agent Server — NorthAdb 课件",
                            canonical=f"web-foundation/{rel_posix}",
                            prose=content, overlay=overlay)
            out.write_text(html, encoding="utf-8", newline="\n")
        elif p.suffix == ".html":
            # iframe 图页与交互实验页：自包含，原样保留
            text = p.read_text(encoding="utf-8")
            out.write_text(text, encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(p, out)

    # ---- hub：站点 hero + 模块/课件/实验/速查卡片（数据解析自 COURSE.md 与 labs）----
    course_md = (src / "COURSE.md").read_text(encoding="utf-8")
    modules = re.findall(
        r"^\| (M\d) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| \[[^\]]+\]\((course/[^)]+)\) \|",
        course_md, re.M)
    secs = []

    def section(label, cards):
        secs.append(f'''  <section class="block wrap">
    <div class="sec-head reveal"><span class="label">{label}</span></div>
    <div class="course-grid reveal">{cards}
    </div>
  </section>''')

    section("课程讲义 · 8 模块", "".join(
        f'''\n        <a class="course-card" href="{url_quote(href, safe='/.#')}">
          <span class="c-badge">{mid}</span>
          <h3>{topic.strip()}</h3>
          <p>{lessons.strip()} · 实验 {labs.strip()}</p>
          <span class="c-link">进入模块 →</span>
        </a>''' for mid, topic, lessons, labs, href in modules))

    lesson_cards = []
    for p in sorted(src.glob("lessons/*.html")):
        m = re.search(r"<h1>([^<]*)</h1>", p.read_text(encoding="utf-8"))
        lesson_cards.append(
            f'''\n        <a class="course-card" href="lessons/{p.name}">
          <span class="c-badge">{p.stem[:4]}</span>
          <h3>{m.group(1) if m else p.stem}</h3>
          <span class="c-link">打开 →</span>
        </a>''')
    section("互动课件", "".join(lesson_cards))

    lab_cards = []
    for p in sorted((src / "labs").glob("*/README.md")):
        m = re.search(r"^# (.+)$", p.read_text(encoding="utf-8"), re.M)
        lab_cards.append(
            f'''\n        <a class="course-card" href="labs/{p.parent.name}/README.html">
          <span class="c-badge">{p.parent.name.split("_")[0]}</span>
          <h3>{m.group(1).strip() if m else p.parent.name}</h3>
          <span class="c-link">进实验 →</span>
        </a>''')
    section(f"实验区 · {len(lab_cards)} 个", "".join(lab_cards))

    section("速查与附录", "".join(
        f'''\n        <a class="course-card" href="{href}">
          <span class="c-badge">{badge}</span>
          <h3>{t}</h3>
          <span class="c-link">查看 →</span>
        </a>''' for badge, t, href in [
            ("SSE", "SSE 速查表", "reference/sse-cheatsheet.html"),
            ("WS", "WebSocket 速查表", "reference/websocket-cheatsheet.html"),
            ("M7", "排障附录", "course/appendix-troubleshooting.html"),
            ("辞", "术语表", "GLOSSARY.html"),
            ("稿", "知识底稿：完整学习路线", "SSE_WebSocket_FastAPI_完整学习路线.html")]))

    hub_body = hero(
        "Course · Web & Infra — 把 Agent 接到网络上",
        '从 HTTP 到实时 <em>Agent Server</em>',
        ('网络通信入门：为什么需要网络通信、异步与 HTTP 地基、SSE 流式、WebSocket 双向、LLM 流式与 Agent 事件，'
         '最后用 Redis 事件总线和 Nginx 把系统推向生产。'
         f'<span class="dim">整理自 <a href="https://github.com/NorthAdb/web_fundation" target="_blank" rel="noopener">NorthAdb/web_fundation</a>，8 模块 / 27 课 / 16 个实验在线可读。</span>'),
        ['<a href="course/module-0-为什么需要网络通信.html" class="btn btn-primary">从模块 0 开始</a>',
         '<a href="COURSE.html" class="btn btn-ghost">课程总纲</a>',
         '<a href="labs/README.html" class="btn btn-ghost">实验区</a>',
         '<a href="https://github.com/NorthAdb/web_fundation" class="btn btn-ghost" target="_blank" rel="noopener">源仓库 ↗</a>'],
        ['<b data-count="8">8</b>个模块',
         '<b data-count="27">27</b>讲课程',
         '<b data-count="16">16</b>个动手实验',
         '<b data-count="9">9</b>张交互架构图']) + "\n" + "\n".join(secs)
    (zone / "index.html").write_text(
        site_shell("../", "从 HTTP 到实时 Agent Server — NorthAdb 的博客",
                   "网络通信入门：异步与 HTTP 地基、SSE 流式、WebSocket 双向通信，到 Agent 事件流与生产化。",
                   "web-foundation/index.html", hub_body, overlay=overlay),
        encoding="utf-8", newline="\n")

    urls = ["web-foundation/index.html"]
    urls += sorted(f"web-foundation/{p.relative_to(zone).as_posix()}"
                   for p in zone.glob("*.html")
                   if p.name != "index.html" and not p.name.startswith("SSE_"))
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
    {"title": "从 HTTP 到实时 Agent Server", "url": "web-foundation/index.html",
     "category": "课件 · 网络通信课",
     "excerpt": "异步与 HTTP 地基、SSE 流式、WebSocket 双向通信，到 Agent 事件流与生产化。",
     "type": "course", "featured": False,
     "keywords": "http sse websocket fastapi redis nginx agent server 网络"},
    {"title": "Web & Infra", "url": "web-foundation/index.html", "category": "方向",
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
