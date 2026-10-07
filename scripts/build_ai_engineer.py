# -*- coding: utf-8 -*-
"""
Build the `ai-engineer/` course zone for northadb.github.io from the cloned
repo `AI-Engineer-from-scrach` (https://github.com/juliepy/AI-Engineer-from-scrach).

Output (into northadb.github.io/):
  ai-engineer/index.html                     hub
  ai-engineer/<chapter>/index.html           chapter doc list
  ai-engineer/<chapter>/<doc>.html           converted notes (site post template)
  ai-engineer/assets/course.css              zone-specific styles (design tokens)
  ai-engineer/assets/mermaid-init.js         mermaid progressive enhancement
  ai-engineer/assets/img/<hash>.<ext>        referenced images, copied
  ai-engineer/assets/vendor/mermaid.min.js   vendored by hand (not here)

Also updates: search.json, sitemap.xml, and the 课件 dropdown in existing pages.
"""
import hashlib
import html as html_mod
import json as json_mod
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote as url_quote

import markdown

# 读入的一切文本归一化：\r\n → LF；剔除 NUL（混入的 \x00 会让 git 把构建产物
# 当二进制、跳过换行归一化，导致本地与 CI 产物入库不一致）
_orig_read_text = Path.read_text
def _read_text_lf(self, *a, **kw):
    return _orig_read_text(self, *a, **kw).replace("\r\n", "\n").replace("\x00", "")
Path.read_text = _read_text_lf

# scripts/ 位于主站仓库内：SITE = 仓库根，WORKSPACE = 仓库的上一级（源仓库 clone 成其兄弟目录）
SITE = Path(__file__).resolve().parent.parent
WORKSPACE = SITE.parent
REPO = WORKSPACE / "AI-Engineer-from-scrach"
ZONE = "ai-engineer"
ZONE_DIR = SITE / ZONE
REPO_URL = "https://github.com/juliepy/AI-Engineer-from-scrach"
REPO_BRANCH = "main"
SITE_URL = "https://northadb.github.io"
TODAY = "2026-10-06"

MD = markdown.Markdown(extensions=["extra", "sane_lists", "toc", "md_in_html"],
                       output_format="html5")

# --------------------------------------------------------------------------
# chapter metadata
# --------------------------------------------------------------------------

def lg(*pats):
    """glob repo-relative patterns (README.md first per directory)"""
    out = []
    for pat in pats:
        for p in sorted(REPO.glob(pat)):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO).as_posix()
            if rel not in out:
                out.append(rel)
    # README.md of each directory sorts before numbered files
    out.sort(key=lambda r: (str(Path(r).parent), 0 if Path(r).name.lower() == "readme.md" else 1, r))
    return out


CHAPTERS = [
    dict(num="00", slug="outline", directory="00-大纲", title="学习总大纲",
         desc="学习顺序总览：工具调用 → ReAct → 规划执行 → 反思 → 树搜索 → 多角色协作，附 multi-agent-arch 课表与目录地图。",
         docs=["00-大纲/Agent教学大纲.md"],
         slug_overrides={"00-大纲/Agent教学大纲.md": "learning-outline"}),
    dict(num="01", slug="agent", directory="01-Agent", title="Agent 核心模式",
         desc="Function Call、ReAct、Plan-and-Execute、Reflexion、LATS 与 Multi-Agent Crew —— 六种核心模式的原理、代码与对比。",
         docs=["01-Agent/README.md",
               "01-Agent/01-small-llm-function-call-project/README.md",
               "01-Agent/02-Agent_react/Readme.md",
               "01-Agent/02-Plan-and-Execute/Readme.md",
               "01-Agent/03-Reﬂexion/Readme.md",
               "01-Agent/04-LATS/Readme.md",
               "01-Agent/05-Multi-Agent-Crew/Readme.md"],
         slug_overrides={"01-Agent/03-Reﬂexion/Readme.md": "03-reflexion"}),
    dict(num="02", slug="rag", directory="02-RAG", title="RAG 全流程",
         desc="从最朴素的向量检索到 High-Level RAG、GraphRAG、RAG 评测与 PDF 解析，一条完整的 RAG 学习线。",
         docs=["02-RAG/01-simple_rag/README.md",
               "02-RAG/02-RAG_basic/README.md",
               "02-RAG/03-high_level_RAG/README.md",
               "02-RAG/03-high_level_RAG/04-graph_rag进阶/README.md",
               "02-RAG/04_RAG_Evaluation/lesson1_rag_evaluation/README.md",
               "02-RAG/04_RAG_Evaluation/lesson2_rag_metrics/README.md",
               "02-RAG/05_PDF_process/README.md"]),
    dict(num="03", slug="memory", directory="03-memory", title="记忆系统",
         desc="窗口记忆、长期记忆、摘要记忆与三因子打分。以代码实践为主，笔记在仓库 03-memory/，此处不设网页。",
         docs=[]),
    dict(num="04", slug="multi-agent", directory="04-multiagent", title="多智能体架构",
         desc="多智能体架构：Pipeline / Hub-Spoke / Blackboard、Supervisor 分层与 HITL，附 AutoGen / CrewAI 实战课表。",
         docs=lg("04-multiagent/multi-agent-arch/README.md")),
    dict(num="05", slug="model-route", directory="05-model-route", title="模型路由",
         desc="模型路由：按成本、能力与场景把请求分发给合适的模型。",
         docs=lg("05-model-route/*.md")),
    dict(num="06", slug="harness", directory="06-harnes", title="Harness 工程化",
         desc="learn-claude-code 二十讲逐节拆解 Agent Loop、工具、权限、压缩、子代理；另有 ragent 多渠道检索与三套工程示例。",
         docs=lg("06-harnes/learn-claude-code/README-zh.md",
                 "06-harnes/learn-claude-code/s[0-9][0-9]_*/README.md",
                 "06-harnes/01-simple_harnes_demo/README.md",
                 "06-harnes/02-rag-harness-demo/README.md",
                 "06-harnes/harness-engineering-demo/README.md",
                 "06-harnes/harness-engineering-demo/ralph/README.md",
                 "06-harnes/ragent/README.md",
                 "06-harnes/ragent/docs/quick-start.md",
                 "06-harnes/ragent/docs/multi-channel-retrieval.md",
                 "06-harnes/ragent/docs/pdf-ingestion-example.md",
                 "06-harnes/ragent/docs/refactoring-summary.md"),
         title_overrides={"06-harnes/ragent/README.md": "Ragent — 后端程序员转型 AI 工程师的多渠道检索 RAG 中台"}),
    dict(num="07", slug="llm-scratch", directory="07-llm_from_scrach", title="从零实现 LLM",
         desc="从零实现大模型：分词、预训练、训练流程图到 GRPO 强化学习。",
         docs=["07-llm_from_scrach/README_cn.md",
               "07-llm_from_scrach/part_1/README.md",
               "07-llm_from_scrach/part_2/train_flowchart.md",
               "07-llm_from_scrach/part_5/README.md",
               "07-llm_from_scrach/part_9/GRPO_TRAINING_EXPLANATION.md",
               "07-llm_from_scrach/tiny model training/README.md"]),
    dict(num="08", slug="hermes", directory="08-hermes-agent", title="Hermes 源码精读",
         desc="Hermes 源码精读：Memory、主循环、Eval、Prompt、环境、Cron、Gateway —— 建立现代 Agent Runtime 心智模型。",
         docs=["08-hermes-agent/03-hermes Agent  学习大纲.md",
               "08-hermes-agent/01-arch.md",
               "08-hermes-agent/02-memory.md",
               "08-hermes-agent/04-arch.md",
               "08-hermes-agent/01-memory/README.md",
               "08-hermes-agent/02-run-agent/README.md",
               "08-hermes-agent/03-eval/README.md",
               "08-hermes-agent/04-prompt/README.md",
               "08-hermes-agent/05-env/README.md",
               "08-hermes-agent/06-cron/README.md",
               "08-hermes-agent/07-mem-provider/README.md",
               "08-hermes-agent/08-gateway/README.md",
               "08-hermes-agent/09-lang-serial-not/README.md",
               "08-hermes-agent/hermes-study/AGENTS.md"],
         slug_overrides={"08-hermes-agent/03-hermes Agent  学习大纲.md": "00-outline",
                         "08-hermes-agent/hermes-study/AGENTS.md": "hermes-study"},
         title_overrides={"08-hermes-agent/03-hermes Agent  学习大纲.md": "Hermes 学习大纲"}),
    dict(num="09", slug="loop", directory="09-loop-engineering", title="Loop Engineering",
         desc="Loop Engineering 三部曲：从 Prompt 到 Context、Harness，再到 Loop 本身的工程化方法论。",
         docs=lg("09-loop-engineering/*.md")),
    dict(num="10", slug="cicd", directory="10-CICD", title="CI/CD 面试突击",
         desc="CI/CD 概念、pytest、GitLab CI、交叉编译与制品、故障排查、Jenkins、工具链与口述话术，附笔试题库。",
         docs=lg("10-CICD/**/*.md")),
    dict(num="11", slug="langgraph", directory="11-langgraph", title="LangGraph 实战",
         desc="LangGraph 实战：从 LangChain 对比、多智能体研究系统到 Agentic Chatbot 与 TripMate 旅行规划。",
         docs=lg("11-langgraph/**/*.md")),
    dict(num="12", slug="waku", directory="12-hermes-agent-small", title="waku 精简四支柱",
         desc="waku（hermes-agent-small）：本地优先教学助手，用最小代码复现 Harness · Loop · Memory · Eval 四支柱。",
         docs=["12-hermes-agent-small/README.md",
               "12-hermes-agent-small/learn_guide.md",
               "12-hermes-agent-small/docs/architecture.md",
               "12-hermes-agent-small/docs/benchmarks.md",
               "12-hermes-agent-small/docs/stack-report.md",
               "12-hermes-agent-small/docs/DEMO-CHECKLIST.md",
               "12-hermes-agent-small/docs/good-first-issues.md",
               "12-hermes-agent-small/evals/deterministic/README.md",
               "12-hermes-agent-small/evals/judge/README.md"]),
    dict(num="13", slug="pi", directory="13-pi-agent", title="Pi 架构与上手",
         desc="Pi 架构与上手十讲：Core / Interactive 双模式、会话树、事件系统、能力扩展与 Skills。",
         docs=lg("13-pi-agent/*.md")),
    dict(num="14", slug="deepseek", directory="14-deepseek-harness", title="DeepSeek Harness",
         desc="DeepSeek Harness 架构笔记。",
         docs=lg("14-deepseek-harness/*.md")),
    dict(num="15", slug="edge", directory="15-Edge-Agent", title="Edge Agent",
         desc="Edge Agent：面向边缘侧的轻量 Agent 架构。",
         docs=lg("15-Edge-Agent/*.md")),
    dict(num="16", slug="notes", directory="99-My idea", title="学习笔记与思考",
         desc="个人学习笔记：长期记忆专题、AI 编程工作流、Agent Eval 与小白岗位学习指南。",
         docs=lg("99-My idea/**/*.md")),
]

COURSE_NAME = "AI Agent 面试宝典"
BILIBILI = "https://space.bilibili.com/524275099"

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def clean_slug(text, fallback="doc"):
    s = re.sub(r"[_.]+", "-", text.lower())
    s = re.sub(r"[^a-z0-9-]+", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or fallback


def doc_slug(rel, override=None, chapter_dir=None):
    if override:
        return clean_slug(override)
    p = Path(rel)
    stem = p.stem
    if stem.lower().startswith("readme"):
        # READMEs are identified by their directory leaf (chapter dir → overview)
        parts = list(p.parent.parts)
        if chapter_dir and parts and parts[0] == chapter_dir:
            parts = parts[1:]
        return clean_slug(parts[-1]) if parts else clean_slug("overview")
    base = clean_slug(stem)
    if base and not re.search(r"[a-z]", base):
        # numeric-only slugs (Chinese titles stripped) get the parent leaf
        base = clean_slug(f"{p.parent.name}-{base}")
    return base


def strip_frontmatter(text):
    m = re.match(r"^\ufeff?---\s*\n.*?\n---\s*\n", text, flags=re.S)
    return text[m.end():] if m else text


def strip_first_h1(text):
    """Remove the leading `# title` line — the page template renders it in the hero."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines[:6]):
        s = line.strip()
        if not s:
            continue
        if re.match(r"^#\s+\S", s):
            del lines[i]
        break
    return "".join(lines)


def get_title(md_text, fallback, converted_html=""):
    for line in md_text.splitlines():
        m = re.match(r"^#\s+(.+?)\s*#*$", line)
        if m:
            return re.sub(r"[`*]", "", m.group(1)).strip()
    if converted_html:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", converted_html, flags=re.S)
        if m:
            t = plain(re.sub(r"<[^>]+>", " ", m.group(1)))
            if t:
                return t
    return fallback


def plain(text):
    text = re.sub(r"[*_`>\[\]()#]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def get_excerpt(md_text):
    skip = 0
    lines = md_text.splitlines()
    # skip the h1 if present
    if lines and lines[0].lstrip().startswith("# "):
        skip = 1
    buf = []
    for line in lines[skip:]:
        s = line.strip()
        if not s:
            if buf:
                break
            continue
        if s.startswith(("#", "![", "|", "```", "---", "<", "> [!")):
            if buf:
                break
            continue
        if re.match(r"^\[.*\]\(.*\)(\s*·\s*\[.*\]\(.*\))*$", s):  # language nav lines
            continue
        if re.match(r"^`{0,2}s\d+`{0,2}\s*→", s):  # learn-claude-code section chain lines
            continue
        if re.match(r"^https?://\S+$", s) and len(buf) == 0:
            continue  # bare link-only lines right after the title
        buf.append(s)
        if sum(len(x) for x in buf) > 160:
            break
    text = plain(" ".join(buf))
    return text[:120] + ("…" if len(text) > 120 else "")


def reading_minutes(md_text):
    cjk = len(re.findall(r"[\u4e00-\u9fff]", md_text))
    words = len(re.findall(r"[A-Za-z0-9]+", md_text))
    return max(1, round(cjk / 400 + words / 220))


# --------------------------------------------------------------------------
# markdown conversion + link/image rewriting
# --------------------------------------------------------------------------

IMG_EXT = {".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp"}
doc_map = {}          # repo-rel md path -> (chapter_slug, page_file)
doc_meta = {}         # repo-rel md path -> dict
copied_images = {}    # repo-rel path -> zone-rel url under assets/img


def convert(md_text):
    MD.reset()
    return MD.convert(md_text)


def gh_blob(rel):
    return f"{REPO_URL}/blob/{REPO_BRANCH}/{url_quote(rel)}"


def gh_tree(rel_dir):
    return f"{REPO_URL}/tree/{REPO_BRANCH}/{url_quote(rel_dir)}"


def rewrite_links(body_html, src_rel, page_zone_rel):
    """page_zone_rel: zone-relative URL dir of the generated page, e.g. 'agent' or ''"""
    body_html = re.sub(r'href="([^"]+)"', lambda m: _rewrite_one(m, "href", src_rel, page_zone_rel), body_html)
    body_html = re.sub(r'src="([^"]+)"', lambda m: _rewrite_one(m, "src", src_rel, page_zone_rel), body_html)
    return body_html


def _rewrite_one(m, attr, src_rel, page_zone_rel):
    raw = m.group(1)
    if raw.startswith(("http://", "https://", "#", "mailto:", "data:", "//")):
        return m.group(0)
    path, _, frag = raw.partition("#")
    if not path:
        return m.group(0)
    base = Path(src_rel).parent
    target = REPO / str(base) / path
    try:
        norm = target.resolve().relative_to(REPO).as_posix()
    except ValueError:
        # link escapes the repo (sibling repo on the author's machine):
        # try to find the basename inside the repo, else point at repo root
        base_name = Path(path).name.rstrip("/")
        hits = [p for p in REPO.glob(f"**/{base_name}*")][:1]
        if hits:
            norm2 = hits[0].relative_to(REPO).as_posix()
            if hits[0].is_dir():
                return f'href="{gh_tree(norm2)}"' if attr == "href" else f'src="{gh_blob(norm2)}"'
            return f'href="{gh_blob(norm2)}"' if attr == "href" else f'src="{gh_blob(norm2)}"'
        return f'href="{REPO_URL}/"' if attr == "href" else m.group(0)
    if attr == "src":
        src_file = REPO / norm
        if src_file.suffix.lower() in IMG_EXT and src_file.exists():
            url = copy_image(norm)
            return f'src="{page_prefix(page_zone_rel)}{url}"'
        return f'src="{gh_blob(norm)}"'
    if norm in doc_map:
        ch, fname = doc_map[norm]
        url = f"{ch}/{fname}" if ch else fname
        anchor = f"#{frag}" if frag else ""
        return f'href="{page_prefix(page_zone_rel)}{url}{anchor}"'
    if (REPO / norm).is_dir():
        return f'href="{gh_tree(norm)}"'
    if (REPO / norm).exists():
        return f'href="{gh_blob(norm)}"'
    if frag:
        return f'href="{gh_blob(norm)}#{frag}"'
    guess = norm.rstrip("/")
    if (REPO / guess).is_dir():
        return f'href="{gh_tree(guess)}"'
    return f'href="{gh_blob(norm)}"'


def page_prefix(zone_dir):
    # prefix that points from page at zone/<zone_dir>/x.html back to zone root
    return "../" if zone_dir else ""


def copy_image(repo_rel):
    if repo_rel in copied_images:
        return copied_images[repo_rel]
    src = REPO / repo_rel
    ext = src.suffix.lower()
    h = hashlib.md5(repo_rel.encode("utf-8")).hexdigest()[:10]
    dest_name = f"{h}{ext}"
    dest_dir = ZONE_DIR / "assets" / "img"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest_dir / dest_name)
    url = f"assets/img/{dest_name}"          # zone-root-relative
    copied_images[repo_rel] = url
    return url


# --------------------------------------------------------------------------
# page shell
# --------------------------------------------------------------------------

FAVICON = ("<link rel=\"icon\" href=\"data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 100 100'><rect width='100' height='100' rx='24' fill='%23FF6363'/>"
           "<text x='50' y='70' font-size='54' text-anchor='middle' fill='%230A0A0A' "
           "font-family='system-ui,sans-serif' font-weight='800'>N</text></svg>\">")


def nav_html(P):
    return f'''<header class="nav" id="nav">
  <div class="nav-inner">
    <a class="brand" href="{P}index.html">
      <span class="brand-mark">N</span>
      <span>NorthAdb</span>
    </a>
    <nav aria-label="主导航">
      <ul class="nav-links" id="navLinks">
        <li><a href="{P}index.html#latest">文章</a></li>
        <li class="nav-drop">
          <a href="{P}learn.html" aria-haspopup="true">课件</a>
          <ul class="drop-menu">
            <li><a href="{P}learn.html"><b>课件总览</b><span>怎么读 · 全部课表</span></a></li>
            <li><a href="{P}ai-engineer/index.html"><b>AI Agent 面试宝典</b><span>17 章 · 面试向全景</span></a></li>
            <li><a href="{P}notes/index.html"><b>我的笔记库</b><span>Obsidian 知识库在线镜像</span></a></li>
            <li><a href="https://northadb.github.io/agent-learning/lessons/"><b>Agent Learning</b><span>主课 · Python 读懂 harness</span></a></li>
            <li><a href="{P}agent-harness-course/index.html"><b>Agent Harness 架构课程</b><span>逆向 Pi 源码 · 15 课</span></a></li>
            <li><a href="{P}learn-pi/index.html"><b>学习 Pi 导读</b><span>中文导读 · 22 篇</span></a></li>
            <li><a href="{P}web-foundation/COURSE.html"><b>从 HTTP 到实时 Agent Server</b><span>网络通信课</span></a></li>
            <li><a href="{P}rag/index.html"><b>RAG Playground</b><span>手写 RAG 流水线</span></a></li>
          </ul>
        </li>
        <li><a href="{P}notes/index.html">笔记库</a><a href="{P}about.html">关于</a></li>
      </ul>
    </nav>
    <div class="nav-actions">
      <button class="search-btn" data-cmdk aria-label="搜索">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
        <span class="search-label">搜索</span>
        <span class="kbd">⌘K</span>
      </button>
      <button class="icon-btn" id="themeToggle" aria-label="切换主题">
        <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>
        <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
      </button>
      <a class="icon-btn" href="https://github.com/NorthAdb" target="_blank" rel="noopener" aria-label="GitHub">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5A11.5 11.5 0 0 0 .5 12a11.5 11.5 0 0 0 7.86 10.92c.58.1.79-.25.79-.56v-2c-3.2.7-3.87-1.36-3.87-1.36-.53-1.32-1.28-1.68-1.28-1.68-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.23-1.28-5.23-5.68 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.41-2.69 5.38-5.25 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.2.67.8.56A11.5 11.5 0 0 0 23.5 12 11.5 11.5 0 0 0 12 .5z"/></svg>
      </a>
    </div>
    <button class="nav-burger" id="navBurger" aria-label="菜单">☰</button>
  </div>
</header>'''


def footer_html(P):
    return f'''<footer class="footer">
  <div class="wrap footer-inner">
    <div class="f-brand">
      <span class="brand-mark">N</span>
      <span>NorthAdb</span>
    </div>
    <nav class="f-links" aria-label="页脚导航">
      <a href="{P}index.html">首页</a>
      <a href="{P}learn.html">课件</a>
      <a href="{P}notes/index.html">笔记库</a>
      <a href="{P}ai-engineer/index.html">面试宝典</a>
      <a href="{P}rag/index.html">RAG</a>
      <a href="{P}about.html">关于</a>
      <a href="{P}feed.xml">RSS</a>
      <a href="https://github.com/NorthAdb" target="_blank" rel="noopener">GitHub</a>
    </nav>
    <p class="f-note">© <span data-year>2025</span> NorthAdb · 理解并构建现代 AI 系统</p>
  </div>
</footer>'''


CMDK = '''<div class="cmdk-overlay" id="cmdk" role="dialog" aria-modal="true" aria-label="搜索">
  <div class="cmdk">
    <input class="cmdk-input" type="text" placeholder="搜索文章、课件与页面…" autocomplete="off" spellcheck="false">
    <ul class="cmdk-list"></ul>
    <div class="cmdk-foot">
      <span><span class="kbd">↑↓</span> 选择</span>
      <span><span class="kbd">↵</span> 打开</span>
      <span><span class="kbd">esc</span> 关闭</span>
    </div>
  </div>
</div>'''


def shell(P, title, desc, canonical_path, body, page_type="post", extra_css=None,
          mermaid=False, ldjson=None):
    extra = f'\n<link rel="stylesheet" href="{P}{ZONE}/assets/course.css">' if extra_css else ""
    ld = f'\n<script type="application/ld+json">\n{ldjson}\n</script>' if ldjson else ""
    mm = ""
    if mermaid:
        mm = (f'\n<script src="{P}{ZONE}/assets/mermaid-init.js" defer></script>')
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_mod.escape(title)}</title>
<meta name="description" content="{html_mod.escape(desc, quote=True)}">
<link rel="canonical" href="{SITE_URL}/{canonical_path}">
<meta name="theme-color" content="#0a0a0a">
<meta property="og:type" content="article">
<meta property="og:site_name" content="NorthAdb">
<meta property="og:title" content="{html_mod.escape(title, quote=True)}">
<meta property="og:description" content="{html_mod.escape(desc, quote=True)}">
<meta property="og:url" content="{SITE_URL}/{canonical_path}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{html_mod.escape(title, quote=True)}">
<meta name="twitter:description" content="{html_mod.escape(desc, quote=True)}">
{FAVICON}
<link rel="alternate" type="application/rss+xml" title="NorthAdb 的博客" href="{P}feed.xml">
<link rel="stylesheet" href="{P}css/style.css">{extra}{ld}
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.setAttribute("data-theme",t);}}catch(e){{}}</script>
</head>
<body data-root="{P}" data-page="{page_type}">

<div class="progress" id="progress"></div>

{nav_html(P)}

<main>
{body}
</main>

{footer_html(P)}

{CMDK}

<button class="to-top" id="toTop" aria-label="回到顶部">↑</button>

{mm}
<script src="{P}js/main.js" defer></script>
</body>
</html>'''


# --------------------------------------------------------------------------
# page builders
# --------------------------------------------------------------------------

def crumb(P, chapter_title=None, chapter_url=None):
    parts = [f'<a href="{P}index.html">首页</a><span>/</span>',
             f'<a href="{P}learn.html">课件</a><span>/</span>',
             f'<a href="{P}{ZONE}/index.html">{COURSE_NAME}</a>']
    if chapter_title and chapter_url:
        parts.append(f'<span>/</span><a href="{chapter_url}">{html_mod.escape(chapter_title)}</a>')
    return '<div class="crumbs">' + "".join(parts) + '</div>'


def build_doc_page(ch, dmeta, body_html, P, prev_doc, next_doc):
    title = dmeta["title"]
    excerpt = dmeta["excerpt"]
    url_path = f"{ZONE}/{ch['slug']}/{dmeta['file']}" if ch["slug"] else f"{ZONE}/{dmeta['file']}"
    canonical = url_path
    ldjson = json_mod.dumps({
        "@context": "https://schema.org", "@type": "TechArticle",
        "headline": title, "description": excerpt,
        "author": {"@type": "Person", "name": "juliepy", "url": REPO_URL},
        "mainEntityOfPage": f"{SITE_URL}/{canonical}",
    }, ensure_ascii=False)

    post_nav = ""
    if prev_doc or next_doc:
        prev_a = ""
        if prev_doc:
            pch, pmeta = prev_doc
            purl = f"{pch['slug']}/{pmeta['file']}" if pch["slug"] else pmeta["file"]
            prev_a = (f'<a class="prev" href="{P}{ZONE}/{purl}"><span class="dir">← 上一篇</span>'
                      f'<span class="t">{html_mod.escape(pmeta["title"])}</span></a>')
        else:
            prev_a = '<span></span>'
        next_a = ""
        if next_doc:
            nch, nmeta = next_doc
            nurl = f"{nch['slug']}/{nmeta['file']}" if nch["slug"] else nmeta["file"]
            next_a = (f'<a class="next" href="{P}{ZONE}/{nurl}"><span class="dir">下一篇 →</span>'
                      f'<span class="t">{html_mod.escape(nmeta["title"])}</span></a>')
        post_nav = f'<div class="wrap"><nav class="post-nav">{prev_a}{next_a}</nav></div>'

    chapter_url = f"{P}{ZONE}/{ch['slug']}/index.html"
    body = f'''  <div class="post-layout">
    <div class="post-main">
      <article>
        <header class="post-hero">
          {crumb(P, ch["title"], chapter_url)}
          <h1>{html_mod.escape(title)}</h1>
          <p class="post-sub">{html_mod.escape(excerpt)}</p>
          <div class="post-meta">
            <span class="avatar">AI</span>
            <span>{COURSE_NAME}</span><span class="sep"></span>
            <span>{html_mod.escape(ch["title"])}</span><span class="sep"></span>
            <span>阅读约 {dmeta["minutes"]} 分钟</span>
          </div>
        </header>

        <div class="toc-mobile">
          <details>
            <summary>On this page</summary>
            <nav class="toc"><div class="toc-build"></div></nav>
          </details>
        </div>

        <div class="prose">
{body_html}
        </div>

        <footer class="post-foot">
          <div class="tags">
            <span class="chip">{html_mod.escape(ch["title"])}</span>
            <span class="chip">AI Agent</span>
            <span class="chip">面试宝典</span>
          </div>
          <a class="t-meta" href="{gh_blob(dmeta['rel'])}" target="_blank" rel="noopener">在 GitHub 查看原文 ↗</a>
        </footer>
      </article>
    </div>

    <aside>
      <nav class="toc" aria-label="目录">
        <div class="toc-title">On this page</div>
        <div class="toc-build"></div>
      </nav>
    </aside>
  </div>

  {post_nav}'''
    return shell(P, f"{title} · {COURSE_NAME} — NorthAdb 的博客", excerpt, canonical,
                 body, page_type="post", extra_css=True, mermaid=dmeta["mermaid"],
                 ldjson=ldjson)


def build_chapter_page(ch, dmetas, P, prev_ch, next_ch):
    ch_url = f"{ZONE}/{ch['slug']}/index.html"
    rows = []
    for i, m in enumerate(dmetas, 1):
        rows.append(f'''      <li>
        <a class="post-row" href="{m['file']}">
          <span class="num">{i:02d}</span>
          <div>
            <h3>{html_mod.escape(m["title"])}</h3>
            <div class="row-meta"><span class="cat">{html_mod.escape(ch["title"])}</span><span class="sep"></span><span>阅读约 {m["minutes"]} 分钟</span></div>
            <p class="row-desc">{html_mod.escape(m["excerpt"])}</p>
          </div>
          <span class="arrow">→</span>
        </a>
      </li>''')
    rows_html = "\n".join(rows)

    nav_cards = []
    if prev_ch:
        nav_cards.append(f'<a class="btn btn-ghost" href="../{prev_ch["slug"]}/index.html">← {html_mod.escape(prev_ch["title"])}</a>')
    if next_ch:
        nav_cards.append(f'<a class="btn btn-ghost" href="../{next_ch["slug"]}/index.html">{html_mod.escape(next_ch["title"])} →</a>')
    nav_row = ('<div class="chapter-nav">' + "".join(nav_cards) + '</div>') if nav_cards else ""

    body = f'''  <section class="hero wrap" style="padding-bottom: 40px;">
    <div class="hero-glow"></div>
    <div class="hero-kicker"><span class="dot"></span> {COURSE_NAME} · 第 {ch["num"]} 章</div>
    <h1 class="t-h1">{html_mod.escape(ch["title"])}</h1>
    <p class="sub">{html_mod.escape(ch["desc"])}<span class="dim">共 {len(dmetas)} 篇笔记，整理自 <a href="{gh_tree(ch['directory'])}" target="_blank" rel="noopener">{ch["directory"]}/</a>。</span></p>
    <div class="hero-actions">
      <a href="{gh_tree(ch["directory"])}" class="btn btn-ghost">源目录 ↗</a>
      <a href="{P}{ZONE}/index.html" class="btn btn-ghost">返回宝典目录 →</a>
    </div>
  </section>

  <section class="block wrap" style="padding-top: 0;">
    <div class="sec-head">
      <span class="label">章节目录</span>
    </div>
    <ul class="post-list">
{rows_html}
    </ul>
  </section>

  <section class="block wrap">
    {nav_row}
  </section>'''
    desc = f"{ch['desc']} {COURSE_NAME}第 {ch['num']} 章，共 {len(dmetas)} 篇笔记。"
    return shell(P, f'{ch["title"]} · {COURSE_NAME} — NorthAdb 的博客', desc, ch_url,
                 body, page_type="", extra_css=True)


def build_hub(total_docs, total_minutes, total_code):
    P = "../"
    cards = []
    for ch in CHAPTERS:
        n = ch["doc_count"]
        if n:
            href = f"{ch['slug']}/index.html"
            badge = ch["num"]
            meta = f"{n} 篇"
            link_label = "进入章节 →"
        else:
            href = gh_tree(ch["directory"])
            badge = ch["num"]
            meta = "代码实践"
            link_label = "在 GitHub 查看 ↗"
        cards.append(f'''      <a class="course-card" href="{href}">
        <span class="c-badge">{badge}</span>
        <h3>{html_mod.escape(ch["title"])}</h3>
        <p>{html_mod.escape(ch["desc"])}</p>
        <span class="c-link">{link_label}</span>
      </a>''')
    cards_html = "\n".join(cards)

    body = f'''  <section class="hero wrap">
    <div class="hero-glow"></div>
    <div class="hero-kicker"><span class="dot"></span> Course · AI Engineer from Scratch</div>
    <h1>{COURSE_NAME.replace("面试宝典", "<em>面试宝典</em>")}</h1>
    <p class="sub">面向 Agent / RAG / 多智能体方向的全景学习手册：从 Function Call 一路走到开源 Agent 源码精读与工程化。
      <span class="dim">整理自 <a href="{REPO_URL}" target="_blank" rel="noopener">juliepy/AI-Engineer-from-scrach</a>，{total_docs} 篇笔记在线可读。</span></p>
    <div class="hero-actions">
      <a href="outline/index.html" class="btn btn-primary">从学习大纲开始</a>
      <a href="{REPO_URL}" class="btn btn-ghost" target="_blank" rel="noopener">源仓库 ↗</a>
      <a href="{BILIBILI}" class="btn btn-ghost" target="_blank" rel="noopener">B 站视频课 ↗</a>
    </div>
    <div class="hero-stats">
      <div><b data-count="17">17</b>个章节</div>
      <div><b data-count="{total_docs}">{total_docs}</b>篇在线笔记</div>
      <div><b data-count="{total_code}" data-suffix="+">{total_code}+</b>个代码示例</div>
      <div><b>0</b>依赖 · 纯静态</div>
    </div>
  </section>

  <section class="block wrap">
    <div class="sec-head reveal">
      <span class="label">学习路径</span>
    </div>
    <div class="course-grid reveal">
{cards_html}
    </div>
  </section>

  <section class="block wrap">
    <div class="about-strip reveal">
      <div class="about-avatar">读</div>
      <div>
        <h3>怎么读这条路径</h3>
        <p>建议按三段推进：<b>打基础</b>（01 Agent 模式 → 02 RAG → 03 记忆 → 04 多智能体 → 05 路由），<b>学工程</b>（06 Harness → 09 Loop Engineering → 10 CI/CD），<b>读源码</b>（先 08 Hermes 建立 Runtime 心智模型，再看 12 waku 的精简四支柱，最后用 13 Pi 对照 TypeScript 实现）。每篇笔记底部都有「在 GitHub 查看原文」，代码与数据集以仓库为准。</p>
        <div class="links">
          <a href="{REPO_URL}" target="_blank" rel="noopener">AI-Engineer-from-scrach ↗</a>
          <a href="{BILIBILI}" target="_blank" rel="noopener">B 站 @作者 ↗</a>
          <a href="outline/index.html">学习总大纲 →</a>
        </div>
      </div>
    </div>
  </section>'''
    desc = (f"{COURSE_NAME}：面向 Agent / RAG / 多智能体面试的全景学习手册，"
            f"17 章 {total_docs} 篇在线笔记，整理自 juliepy/AI-Engineer-from-scrach。")
    return shell(P, f"{COURSE_NAME} — NorthAdb 的博客", desc, f"{ZONE}/index.html",
                 body, page_type="", extra_css=True)


# --------------------------------------------------------------------------
# static assets written by the generator
# --------------------------------------------------------------------------

COURSE_CSS = '''/* ============================================================
   AI Agent 面试宝典 — course-zone overlay
   Built on the site design tokens (css/style.css). No new colors.
   ============================================================ */

/* mermaid host: appears only after a successful render replaces the code block */
.mermaid {
  display: flex;
  justify-content: center;
  padding: 1.4em 1.2em;
  margin: 1.8em 0;
  background: var(--code-bg);
  border: 1px solid var(--code-border);
  border-radius: var(--r-md);
  overflow-x: auto;
}
.mermaid svg { max-width: 100%; height: auto; }

/* chapter index: give every row a readable excerpt */
.post-list .row-desc {
  margin: 6px 0 0;
  font-size: 13.5px;
  color: var(--text-3);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* prev/next chapter strip on chapter pages */
.chapter-nav {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

/* hub: slightly denser grid now that there are 17 cards */
.ae-path .course-grid { grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
'''

MERMAID_INIT = '''/* AI Agent 面试宝典 — mermaid progressive enhancement.
   Fenced ```mermaid blocks stay as plain code blocks; this script swaps
   them for rendered SVG only when vendored mermaid loads. Failure keeps
   the readable code block. Re-renders on theme change. */
(function () {
  "use strict";
  var codes = Array.prototype.slice.call(
    document.querySelectorAll(".prose pre code.language-mermaid")
  );
  if (!codes.length) return;

  var root = document.body.getAttribute("data-root") || "";
  var sources = codes.map(function (code) {
    return { pre: code.parentElement, src: code.textContent, host: null };
  });

  function themeName() {
    return document.documentElement.getAttribute("data-theme") === "light" ? "default" : "dark";
  }

  function renderAll() {
    if (!window.mermaid || !window.mermaid.render) return;
    try {
      mermaid.initialize({
        startOnLoad: false,
        theme: themeName(),
        fontFamily: 'ui-sans-serif, system-ui, "PingFang SC", "Microsoft YaHei", sans-serif'
      });
    } catch (e) { return; }
    sources.forEach(function (o, i) {
      mermaid.render("ae-diagram-" + i, o.src).then(function (res) {
        if (!o.host) {
          o.host = document.createElement("div");
          o.host.className = "mermaid";
        }
        o.host.innerHTML = res.svg;
        if (o.pre && o.pre.parentNode) {
          o.pre.parentNode.replaceChild(o.host, o.pre);
          o.pre = null;
        }
      }).catch(function () { /* keep the code block */ });
    });
  }

  var s = document.createElement("script");
  s.src = root + "ai-engineer/assets/vendor/mermaid.min.js";
  s.defer = true;
  s.onload = renderAll;
  document.head.appendChild(s);

  try {
    new MutationObserver(renderAll).observe(document.documentElement, {
      attributes: true, attributeFilter: ["data-theme"]
    });
  } catch (e) {}
})();
'''

# --------------------------------------------------------------------------
# integration into existing site files
# --------------------------------------------------------------------------

def add_nav_item(path):
    """Insert the AI 宝典 entry into the 课件 dropdown of an existing page."""
    text = path.read_text(encoding="utf-8")
    if "<b>AI Agent 面试宝典</b>" in text:
        return "already"
    m = re.search(r'<li><a href="((?:\.\./)*)rag/index\.html">.*?</a></li>', text)
    if not m:
        return "no-anchor"
    P = m.group(1)
    new_item = (f'\n            <li><a href="{P}{ZONE}/index.html"><b>AI Agent 面试宝典</b>'
                f'<span>17 章 · 面试向全景</span></a></li>')
    patched = text[:m.end()] + new_item + text[m.end():]
    if "ai-engineer/index.html" not in patched:
        return "insert-failed"
    path.write_text(patched, encoding="utf-8")
    return "ok"


def update_search_json(entries):
    path = SITE / "search.json"
    old = path.read_text(encoding="utf-8")
    data = old.rstrip()
    assert data.startswith("[")
    import json
    items = json.loads(data)
    items = [i for i in items if not str(i.get("url", "")).startswith(ZONE + "/")
             and not str(i.get("url", "")).startswith(REPO_URL)]
    items.extend(entries)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_sitemap(urls):
    path = SITE / "sitemap.xml"
    text = path.read_text(encoding="utf-8")
    # 整块删除本 zone 的 url；旧的按行过滤只删了 <loc> 行，会泄漏 <lastmod> 残块且逐次累积
    text = re.sub(
        rf"  <url>\n    <loc>{SITE_URL}/{ZONE}/[^<]*</loc>\n    <lastmod>[^<]*</lastmod>\n  </url>\n",
        "", text)
    # 一次性清理历史残块（无 <loc> 的空 <url> 块）
    text = re.sub(r"  <url>\n    <lastmod>[^<]*</lastmod>\n  </url>\n", "", text)
    block = "".join(
        f"  <url>\n    <loc>{SITE_URL}/{u}</loc>\n    <lastmod>{TODAY}</lastmod>\n  </url>\n"
        for u in urls)
    text = text.replace("</urlset>", block + "</urlset>")
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    # Windows can hold a handle on the zone root itself (shell CWD / indexer);
    # keep the root dir and clear its children instead of rmtree'ing it.
    ZONE_DIR.mkdir(parents=True, exist_ok=True)
    import time
    for child in list(ZONE_DIR.iterdir()):
        for attempt in range(8):
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                break
            except PermissionError:
                time.sleep(1.5)
        else:
            raise RuntimeError(f"locked: {child}")
    (ZONE_DIR / "assets" / "vendor").mkdir(parents=True, exist_ok=True)
    vend = WORKSPACE / "mermaid.min.js"
    if not vend.exists():
        vend = SITE / "mermaid.min.js"
    if vend.exists():
        shutil.copyfile(vend, ZONE_DIR / "assets" / "vendor" / "mermaid.min.js")

    # ---- register docs ----
    reading_seq = []   # (chapter, meta) in global reading order
    for ch in CHAPTERS:
        used = set()
        metas = []
        for rel in ch["docs"]:
            src = REPO / rel
            if not src.exists():
                print(f"  !! missing: {rel}")
                continue
            override = ch.get("slug_overrides", {}).get(rel)
            slug = doc_slug(rel, override, ch["directory"])
            base = slug
            k = 2
            while slug in used:
                slug = f"{base}-{k}"
                k += 1
            used.add(slug)
            raw = strip_frontmatter(src.read_text(encoding="utf-8", errors="replace"))
            fb = Path(rel).stem
            if fb.lower().startswith("readme"):
                fb = Path(rel).parent.name
            title = ch.get("title_overrides", {}).get(rel) or get_title(raw, fb)
            metas.append(dict(rel=rel, slug=slug, file=f"{slug}.html", title=title,
                              fallback=fb,
                              excerpt=get_excerpt(raw), minutes=reading_minutes(raw),
                              mermaid="```mermaid" in raw))
            doc_map[rel] = (ch["slug"], f"{slug}.html")
        ch["metas"] = metas
        ch["doc_count"] = len(metas)
        for m in metas:
            reading_seq.append((ch, m))

    # ---- convert docs (with prev/next in global reading order) ----
    total = 0
    for idx, (ch, m) in enumerate(reading_seq):
        out_dir = ZONE_DIR / ch["slug"] if ch["slug"] else ZONE_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        prev_doc = reading_seq[idx - 1] if idx > 0 else None
        next_doc = reading_seq[idx + 1] if idx < len(reading_seq) - 1 else None
        src = REPO / m["rel"]
        raw = strip_frontmatter(src.read_text(encoding="utf-8", errors="replace"))
        body = convert(strip_first_h1(raw))
        body = rewrite_links(body, m["rel"], ch["slug"])
        if not ch.get("title_overrides", {}).get(m["rel"]):
            m["title"] = get_title(raw, m.get("fallback", m["title"]), body)
        html = build_doc_page(ch, m, body, "../../", prev_doc, next_doc)
        (out_dir / m["file"]).write_text(html, encoding="utf-8")
        total += 1

    # ---- chapter pages ----
    chs_with_pages = [c for c in CHAPTERS if c["doc_count"]]
    for i, ch in enumerate(chs_with_pages):
        prev_ch = chs_with_pages[i - 1] if i > 0 else None
        next_ch = chs_with_pages[i + 1] if i < len(chs_with_pages) - 1 else None
        html = build_chapter_page(ch, ch["metas"], "../../", prev_ch, next_ch)
        (ZONE_DIR / ch["slug"]).mkdir(parents=True, exist_ok=True)
        (ZONE_DIR / ch["slug"] / "index.html").write_text(html, encoding="utf-8")

    # ---- hub ----
    total_docs = sum(c["doc_count"] for c in CHAPTERS)
    total_minutes = sum(m["minutes"] for c in CHAPTERS for m in c["metas"])
    total_code = sum(1 for p in REPO.rglob("*") if p.suffix in
                     {".py", ".ipynb", ".ts", ".tsx", ".js", ".java", ".sh"})
    (ZONE_DIR / "index.html").write_text(
        build_hub(total_docs, total_minutes, total_code), encoding="utf-8")

    # ---- assets ----
    (ZONE_DIR / "assets" / "course.css").write_text(COURSE_CSS, encoding="utf-8")
    (ZONE_DIR / "assets" / "mermaid-init.js").write_text(MERMAID_INIT, encoding="utf-8")

    # ---- search.json ----
    import json
    entries = [
        {"title": COURSE_NAME, "url": f"{ZONE}/index.html", "category": "课件 · 17 章",
         "excerpt": "面向 Agent / RAG / 多智能体面试的全景学习手册，整理自 AI-Engineer-from-scrach。",
         "type": "course", "featured": True,
         "keywords": "agent rag memory multiagent harness loop hermes pi waku cicd langgraph 面试 宝典 deepseek edge"},
    ]
    for ch in CHAPTERS:
        if not ch["doc_count"]:
            entries.append({"title": ch["title"],
                            "url": gh_tree(ch["directory"]),
                            "category": f"面试宝典 · 第 {ch['num']} 章 · 代码实践",
                            "excerpt": ch["desc"], "type": "course", "featured": False,
                            "keywords": ch["title"]})
            continue
        entries.append({"title": f'第 {ch["num"]} 章 · {ch["title"]}',
                        "url": f"{ZONE}/{ch['slug']}/index.html",
                        "category": f"面试宝典 · {ch['doc_count']} 篇",
                        "excerpt": ch["desc"], "type": "course", "featured": False,
                        "keywords": ch["title"]})
        for m in ch["metas"]:
            entries.append({"title": m["title"], "url": f"{ZONE}/{ch['slug']}/{m['file']}",
                            "category": f"面试宝典 · {ch['title']}",
                            "excerpt": m["excerpt"], "type": "course", "featured": False,
                            "keywords": ch["title"]})
    update_search_json(entries)

    # ---- sitemap ----
    urls = [f"{ZONE}/index.html"] + [
        f"{ZONE}/{ch['slug']}/index.html" for ch in CHAPTERS if ch["doc_count"]
    ] + [f"{ZONE}/{ch['slug']}/{m['file']}" for ch in CHAPTERS for m in ch["metas"]]
    update_sitemap(urls)

    # ---- nav dropdown in existing pages ----
    nav_targets = [SITE / "index.html", SITE / "learn.html", SITE / "about.html",
                   SITE / "404.html", *sorted((SITE / "posts").glob("*.html"))]
    for t in nav_targets:
        if t.exists():
            print(f"nav {t.name}: {add_nav_item(t)}")

    # ---- report ----
    img_bytes = sum(f.stat().st_size for f in (ZONE_DIR / "assets" / "img").glob("*")) \
        if (ZONE_DIR / "assets" / "img").exists() else 0
    print(f"\ndocs: {total}  chapters: {len(CHAPTERS)}  images copied: {len(copied_images)} "
          f"({img_bytes / 1e6:.1f} MB)  code files: {total_code}")
    for ch in CHAPTERS:
        print(f"  {ch['num']} {ch['slug']:<12} {ch['doc_count']:>3} 篇  {ch['directory']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
