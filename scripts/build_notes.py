# -*- coding: utf-8 -*-
"""
Build the `notes/` zone for northadb.github.io from the cloned Obsidian vault
`north-my-note` (https://github.com/NorthAdb/north-my-note).

Output (into northadb.github.io/):
  notes/index.html                    hub（hero + 分区卡片 + README「关于本库」）
  notes/<section>/index.html          分区页（可选 overview + 按目录分组列表）
  notes/<section>/<path>/<note>.html  转换后的笔记页（站点 post 模板）
  notes/assets/notes.css              分区样式（只用站点设计令牌）
  notes/assets/mermaid-init.js        mermaid 渐进增强（复用 ai-engineer 机制）
  notes/assets/vendor/mermaid.min.js  从工作区 vendor
  notes/assets/img/<hash>.<ext>       引用到的图片

Also updates: search.json, sitemap.xml, and the 课件 dropdown + footer of
existing pages (top-level / posts/ / ai-engineer/**).

URL convention: every emitted in-zone link is `P + "notes/" + zone_rel` where
P is the page's site-root prefix ("../" per directory depth). pg["url"] is
zone-relative (e.g. "domains/nginx-notes.html").
"""
import hashlib
import html as html_mod
import json as json_mod
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import quote as url_quote

import markdown

# 读入的一切文本归一化：\r\n → LF；剔除 NUL（vault 个别文件混入 \x00 会让 git
# 把构建产物当二进制、跳过换行归一化，导致本地与 CI 产物入库不一致）
_orig_read_text = Path.read_text
def _read_text_lf(self, *a, **kw):
    return _orig_read_text(self, *a, **kw).replace("\r\n", "\n").replace("\x00", "")
Path.read_text = _read_text_lf

# scripts/ 位于主站仓库内：SITE = 仓库根，WORKSPACE = 仓库的上一级（vault clone 成其兄弟目录）
SITE = Path(__file__).resolve().parent.parent
WORKSPACE = SITE.parent
VAULT = WORKSPACE / "north-my-note"
ZONE = "notes"
ZONE_DIR = SITE / ZONE
VAULT_URL = "https://github.com/NorthAdb/north-my-note"
VAULT_BRANCH = "main"
SITE_URL = "https://northadb.github.io"
TODAY = "2026-10-06"
ZONE_NAME = "我的笔记库"

# 全部收录 —— 内容在公开仓库里本就可见。想下线某分区，把 slug 加进 SKIP_SECTIONS。
SKIP_SECTIONS: set[str] = set()

SECTIONS = [
    dict(dir="领域", slug="domains", title="知识领域",
         desc="跨项目的知识沉淀：Agent、RAG、Harness、记忆系统的概念笔记与技术选型，以及各条学习路线。"),
    dict(dir="项目", slug="projects", title="项目笔记",
         desc="按项目归集的实践笔记：claude-code-best-practice 实践库、learn-claude-code-north 二十讲、AI-Agents-in-Depth 精读与 Javase 学习。"),
    dict(dir="Clippings", slug="clippings", title="内容剪藏",
         desc="外部内容剪藏与整理：Bilibili、微信公众号、小红书、GitHub、抖音、飞书文档等来源的摘要笔记。"),
    dict(dir="JD", slug="jd", title="JD 情报",
         desc="2026–2027 实习岗位 JD 整理：各大厂岗位要求原文与提炼出的学习路径。"),
    dict(dir="wiki", slug="wiki", title="LLM Wiki",
         desc="Karpathy LLM Wiki 的中文知识库：concepts / entities / sources 三层结构的主题 wiki。"),
    dict(dir="doc-pqsectunnel", slug="pqsectunnel", title="PQ-SecTunnel",
         desc="PQ-SecTunnel 后量子 VPN 项目：WireGuard 背景研究、协议拆解与答辩文档。"),
    dict(dir="claude-memory", slug="memory", title="Claude 记忆",
         desc="Claude Code 长期记忆库（autoMemoryDirectory 指向本目录）。"),
    dict(dir="日记", slug="diary", title="日记",
         desc="每日随记与流水日志。"),
]

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def uni_slugify(value, separator="-"):
    """Heading slug that keeps CJK — shared by the toc extension and wikilinks."""
    v = value.strip().lower()
    v = re.sub(r"[`*_~]", "", v)
    v = re.sub(r"\s+", separator, v)
    v = re.sub(r"[^\w-]+", "", v)  # \w keeps CJK/underscore in py3
    v = re.sub(r"-{2,}", separator, v).strip(separator)
    return v or "section"


MD = markdown.Markdown(
    extensions=["extra", "sane_lists", "toc", "md_in_html"],
    extension_configs={"toc": {"slugify": uni_slugify}},
    output_format="html5")


def clean_slug(text, fallback=""):
    s = re.sub(r"[_.]+", "-", text.lower())
    s = re.sub(r"[^a-z0-9-]+", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or fallback


def seg_slug(text):
    s = clean_slug(text)
    if s:
        return s
    return "p" + hashlib.md5(text.encode("utf-8")).hexdigest()[:6]


def plain(text):
    text = re.sub(r"[*_`>\[\]()#]", "", text)
    return re.sub(r"\s+", " ", text).strip()


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


def get_excerpt(md_text):
    lines = md_text.splitlines()
    skip = 1 if (lines and lines[0].lstrip().startswith("# ")) else 0
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
        if re.match(r"^https?://\S+$", s) and not buf:
            continue
        buf.append(s)
        if sum(len(x) for x in buf) > 160:
            break
    text = plain(" ".join(buf))
    return text[:120] + ("…" if len(text) > 120 else "")


def reading_minutes(md_text):
    cjk = len(re.findall(r"[\u4e00-\u9fff]", md_text))
    words = len(re.findall(r"[A-Za-z0-9]+", md_text))
    return max(1, round(cjk / 400 + words / 220))


def fm_parse(text):
    """Split YAML frontmatter; return (meta, body). Only the fields we show."""
    meta = {}
    m = re.match(r"^\ufeff?---\s*\n(.*?)\n---\s*\n", text, flags=re.S)
    if not m:
        return meta, text
    fm, body = m.group(1), text[m.end():]
    tm = re.search(r"^tags:\s*\[(.*?)\]\s*$", fm, flags=re.M) \
        or re.search(r"^tags:\s*(\S.+)$", fm, flags=re.M)
    if tm:
        meta["tags"] = [t.strip().strip("'\"") for t in tm.group(1).split(",") if t.strip()]
    for field in ("created", "updated", "title"):
        fm_m = re.search(rf"^{field}:\s*[\"']?(.+?)[\"']?\s*$", fm, flags=re.M)
        if fm_m:
            meta[field] = fm_m.group(1).strip()
    return meta, body


def headings_of(body):
    """slug set of all headings (fences skipped) for wikilink #anchor checks."""
    out = set()
    for in_fence, line in md_segments(body):
        if in_fence:
            continue
        m = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if m:
            t = m.group(1)
            t = re.sub(r"\[\[([^\[\]]+)\]\]", lambda mm: mm.group(1).split("|")[-1], t)
            t = re.sub(r"[*`~=]", "", t)
            out.add(uni_slugify(t))
    return out


def strip_first_h1(text):
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines[:6]):
        s = line.strip()
        if not s:
            continue
        if re.match(r"^#\s+\S", s):
            del lines[i]
        break
    return "".join(lines)


# --------------------------------------------------------------------------
# vault model
# --------------------------------------------------------------------------

pages = []            # all notes (+ pdf asset rows), in vault order
sec_overview = {}     # section slug -> overview raw md (or None)
name_map = {}         # basename lower -> page (shortest path wins)
rel_map = {}          # rel-without-ext lower -> page
asset_map = {}        # basename lower -> vault-relative path (png/pdf/...)
copied_images = {}    # vault rel -> site-root-relative url under notes/assets/img
dead_links = []       # (src_rel, target)
open_embeds = []      # (src_rel, name)


def register(pg, name_lists):
    pages.append(pg)
    stem = Path(pg["rel"]).stem.lower()
    name_lists.setdefault(stem, []).append(pg)
    if not pg.get("asset"):
        rel_map[pg["rel"][:-3].lower()] = pg


def discover():
    name_lists = {}
    used_slugs = set()

    # vault-root README feeds the hub「关于本库」
    root_readme = VAULT / "README.md"
    if root_readme.exists():
        raw = root_readme.read_text(encoding="utf-8", errors="replace")
        meta, body = fm_parse(raw)
        register(dict(rel="README.md", section=None, url="index.html",
                      title="关于 north-my-note", body=body, meta=meta), name_lists)

    for sec in SECTIONS:
        if sec["slug"] in SKIP_SECTIONS:
            continue
        root = VAULT / sec["dir"]
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.md"), key=lambda p: p.parts):
            rel = p.relative_to(VAULT).as_posix()
            parts = Path(rel).parts
            sub = parts[1:-1]                       # dirs below the section
            stem = p.stem
            # section-root index.md becomes the section overview, not a page
            if stem.lower() == "index" and not sub:
                sec_overview[sec["slug"]] = p.read_text(encoding="utf-8", errors="replace")
                continue
            dirs = [seg_slug(x) for x in sub]
            if stem.lower() == "readme":
                base = seg_slug(sub[-1] if sub else sec["dir"])
            elif stem.lower() == "index" and sub:
                base = seg_slug(sub[-1])
            else:
                base = seg_slug(stem)
            slug, k = base, 2
            while (sec["slug"], tuple(dirs), slug) in used_slugs:
                slug = f"{base}-{k}"
                k += 1
            used_slugs.add((sec["slug"], tuple(dirs), slug))
            zone_url = "/".join([sec["slug"], *dirs, f"{slug}.html"])
            # site-root prefix depth: notes/ + section + subdirs
            depth = 2 + len(dirs)
            raw = p.read_text(encoding="utf-8", errors="replace")
            meta, body = fm_parse(raw)
            fb = stem if not stem.lower().startswith("readme") else (sub[-1] if sub else sec["title"])
            title = get_title(body, meta.get("title") or fb)
            register(dict(rel=rel, section=sec, url=zone_url, title=title,
                          body=body, meta=meta, depth=depth,
                          headings=headings_of(body)), name_lists)

    for key, lst in name_lists.items():
        lst.sort(key=lambda pg: (pg["rel"].count("/"), pg["rel"]))
        name_map[key] = lst[0]

    for p in VAULT.rglob("*"):
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"}:
            rel_parts = p.relative_to(VAULT).parts
            if any(part.startswith(".") for part in rel_parts):
                continue
            asset_map.setdefault(p.name.lower(), p.relative_to(VAULT).as_posix())


# --------------------------------------------------------------------------
# markdown conversion + link rewriting
# --------------------------------------------------------------------------

IMG_EXT = {".png", ".svg", ".jpg", ".jpeg", ".gif", ".webp"}
CODE_RE = re.compile(r"(`[^`\n]*`)")  # capturing group: split keeps the code spans
EMB_RE = re.compile(r"!\[\[([^\[\]]+)\]\]")
WL_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
MARK_RE = re.compile(r"(?<![=])==(\S(?:[^=\n]*?\S)?)==(?!=[\w])")

FENCE_OPEN_RE = re.compile(r"^\s*(`{3,}|~{3,})")
FENCE_CLOSE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")


def md_segments(text):
    """Yield (in_fence, line) with CommonMark fence tracking: a closer must
    use the same char and be at least as long as the opener."""
    fence_char, fence_len = None, 0
    for line in text.split("\n"):
        if fence_char is None:
            m = FENCE_OPEN_RE.match(line)
            if m:
                fence_char, fence_len = m.group(1)[0], len(m.group(1))
                yield (True, line)
            else:
                yield (False, line)
        else:
            m2 = FENCE_CLOSE_RE.match(line)
            if m2 and m2.group(1)[0] == fence_char and len(m2.group(1)) >= fence_len:
                fence_char = None
            yield (True, line)


def has_display_math(body):
    joined = "\n".join(l for f, l in md_segments(body) if not f)
    return bool(re.search(r"\$\$.*?\$\$", joined, flags=re.S))


def resolve_wl(target):
    """Obsidian-style resolution: exact rel, path suffix, then basename."""
    t = target.strip().replace("\\", "/")
    if t.lower().endswith(".md"):
        t = t[:-3]
    tl = t.lower()
    if not tl:
        return None
    if tl in rel_map:
        return rel_map[tl]
    if "/" in tl:
        for k, pg in rel_map.items():
            if k.endswith("/" + tl):
                return pg
    return name_map.get(tl.rsplit("/", 1)[-1])


def zone_href(pg, P):
    return f"{P}{ZONE}/{pg['url']}"


def wl_html(inner, cur):
    inner = inner.replace("\\|", "|")
    segs = inner.split("|")
    target = segs[0].strip()
    alias = segs[1].strip() if len(segs) > 1 and segs[1].strip() else ""
    tpath, _, frag = target.partition("#")
    if not alias:
        alias = frag if (frag and not tpath) else tpath
    disp = html_mod.escape(alias or target)

    if not tpath:  # [[#heading]] — same page
        if frag and uni_slugify(frag) in cur["headings"]:
            return f'<a class="wl" href="#{uni_slugify(frag)}">{disp}</a>'
        dead_links.append((cur["rel"], target))
        return f'<span class="wl dead" title="未找到对应标题">{disp}</span>'

    pg = resolve_wl(tpath)
    if pg is None:
        asset = asset_map.get(tpath.lower()) or asset_map.get(Path(tpath).name.lower())
        if asset:
            if Path(asset).suffix.lower() in IMG_EXT:
                return f'<a class="wl" href="{cur["P"]}{copy_image(asset)}">{disp}</a>'
            return f'<a class="wl" href="{gh_blob(asset)}">{disp}</a>'
        dead_links.append((cur["rel"], target))
        return f'<span class="wl dead" title="未创建的笔记">{disp}</span>'

    href = zone_href(pg, cur["P"])
    if frag:
        anchor = uni_slugify(frag)
        if anchor in pg["headings"]:
            href += f"#{anchor}"
    return f'<a class="wl" href="{href}">{disp}</a>'


def emb_html(inner, cur):
    inner = inner.replace("\\|", "|")
    segs = inner.split("|")
    target = segs[0].strip()
    size = segs[1].strip() if len(segs) > 1 else ""
    tpath, _, frag = target.partition("#")
    style = f' style="max-width:{size}px"' if size.isdigit() else ""

    asset = asset_map.get(tpath.lower()) or asset_map.get(Path(tpath).name.lower())
    if asset and Path(asset).suffix.lower() in IMG_EXT:
        url = copy_image(asset)
        return f'<img src="{cur["P"]}{url}" alt="{html_mod.escape(tpath)}"{style}>'

    pg = resolve_wl(tpath)
    if pg is not None:
        return f'<a class="wl" href="{zone_href(pg, cur["P"])}">📄 {html_mod.escape(pg["title"])}</a>'

    open_embeds.append((cur["rel"], target))
    return (f'<span class="wl dead" title="附件未入库">🖼️ {html_mod.escape(tpath)}'
            f' <small>（附件未入库）</small></span>')


def transform_line(line, cur):
    parts = CODE_RE.split(line)
    out = []
    for i, seg in enumerate(parts):
        if i % 2:  # inside inline code — untouched
            out.append(seg)
            continue
        seg = MARK_RE.sub(r"<mark>\1</mark>", seg)
        seg = EMB_RE.sub(lambda m: emb_html(m.group(1), cur), seg)
        seg = WL_RE.sub(lambda m: wl_html(m.group(1), cur), seg)
        out.append(seg)
    return "".join(out)


def preprocess_md(text, cur):
    # callout 标题行后补一个空引用行，让紧随的列表/段落正确分块
    text = re.sub(r"(?m)^([ \t]*>[ \t]*\[!\w+\][^\n]*)\n(?=[ \t]*>[ \t]*\S)",
                  r"\1\n>\n", text)
    out = []
    for in_fence, line in md_segments(text):
        out.append(line if in_fence else transform_line(line, cur))
    return "\n".join(out)


def convert(md_text):
    MD.reset()
    return MD.convert(md_text)


def gh_blob(rel):
    return f"{VAULT_URL}/blob/{VAULT_BRANCH}/{url_quote(rel)}"


def gh_tree(rel_dir):
    return f"{VAULT_URL}/tree/{VAULT_BRANCH}/{url_quote(rel_dir)}"


def copy_image(vault_rel):
    if vault_rel in copied_images:
        return copied_images[vault_rel]
    src = VAULT / vault_rel
    ext = src.suffix.lower()
    h = hashlib.md5(vault_rel.encode("utf-8")).hexdigest()[:10]
    dest_dir = ZONE_DIR / "assets" / "img"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest_dir / f"{h}{ext}")
    url = f"{ZONE}/assets/img/{h}{ext}"       # site-root-relative
    copied_images[vault_rel] = url
    return url


def rewrite_links(body_html, cur):
    body_html = re.sub(r'href="([^"]+)"', lambda m: _rewrite_one(m, "href", cur), body_html)
    body_html = re.sub(r'src="([^"]+)"', lambda m: _rewrite_one(m, "src", cur), body_html)
    return body_html


def _rewrite_one(m, attr, cur):
    raw = m.group(1)
    if raw.startswith(("http://", "https://", "#", "mailto:", "data:", "//")):
        return m.group(0)
    # links the generator itself just emitted (../notes/… from any depth) —
    # must not be re-resolved against the vault
    stripped = re.sub(r"^(?:\.\./)+", "", raw)
    if stripped == ZONE or stripped.startswith(ZONE + "/"):
        return m.group(0)
    path, _, frag = raw.partition("#")
    if not path:
        return m.group(0)
    base = Path(cur["rel"]).parent
    target = VAULT / str(base) / path
    try:
        norm = target.resolve().relative_to(VAULT).as_posix()
    except ValueError:
        return m.group(0)
    if attr == "src":
        src_file = VAULT / norm
        if src_file.suffix.lower() in IMG_EXT and src_file.exists():
            return f'src="{cur["P"]}{copy_image(norm)}"'
        return f'src="{gh_blob(norm)}"'
    key = norm[:-3].lower() if norm.lower().endswith(".md") else norm.lower()
    pg = rel_map.get(key) or (resolve_wl(norm) if norm.lower().endswith(".md") else None)
    if pg is not None:
        anchor = f"#{frag}" if frag else ""
        return f'href="{zone_href(pg, cur["P"])}{anchor}"'
    if (VAULT / norm).is_dir():
        return f'href="{gh_tree(norm)}"'
    return f'href="{gh_blob(norm)}"'


CALLOUT_LABELS = {
    "note": "Note", "info": "Info", "important": "Important", "warning": "Warning",
    "tip": "Tip", "abstract": "Abstract", "example": "Example", "quote": "Quote",
    "question": "Question", "success": "Success", "danger": "Danger", "bug": "Bug",
}
BQ_RE = re.compile(r"<blockquote>(.*?)</blockquote>", re.S)
BQ_HEAD_RE = re.compile(r"\s*<p>\[!(\w+)\][+-]?\s*(.*?)</p>", re.S)


def fix_callouts(body_html):
    """Blockquote(s) may hold several [!type] paragraphs (python-markdown
    merges adjacent blockquotes) — split at each and emit one div each."""
    def build(ctype, first_p, after):
        parts = first_p.split("\n", 1)
        title = parts[0].strip() or CALLOUT_LABELS.get(ctype, ctype)
        body_open = f"<p>{parts[1]}</p>" if len(parts) > 1 and parts[1].strip() else ""
        return (f'<div class="callout" data-callout="{ctype}">'
                f'<p class="callout-title">{html_mod.escape(title)}</p>{body_open}{after}</div>')

    def repl(m):
        inner = m.group(1)
        if not re.search(r"<p>\[!\w+\]", inner):
            return m.group(0)
        out = []
        for part in re.split(r"(?=<p>\[!\w+\])", inner):
            head = BQ_HEAD_RE.match(part)
            if not head:
                out.append(part)
                continue
            out.append(build(head.group(1).lower(), head.group(2), part[head.end():]))
        return "".join(out)

    return BQ_RE.sub(repl, body_html)


def fix_tasks(body_html):
    body_html = re.sub(r"<li>\[ \]\s*", '<li class="task"><span class="cb" aria-hidden="true"></span>', body_html)
    body_html = re.sub(r"<li>\[[xX]\]\s*", '<li class="task done"><span class="cb" aria-hidden="true"></span>', body_html)
    return body_html


IMG_TAG_RE = re.compile(r'<img [^>]*src="(?P<src>[^"]*/blob/[^"]*)"[^>]*>')


def fix_imgs(body_html):
    # 1) images pointing at vault files that were never committed → the blob
    #    URL is an HTML page (404), useless as src; show a placeholder instead
    def repl(m):
        name = m.group("src").rsplit("/", 1)[-1]
        from urllib.parse import unquote
        name = unquote(name)
        return (f'<span class="img-missing" title="附件未提交到仓库">🖼️ '
                f'{html_mod.escape(name)}<small>（附件未入库）</small></span>')
    body_html = IMG_TAG_RE.sub(repl, body_html)
    # 2) gitee 等图床按 Referer 防盗链：跨域 <img> 默认带 Referer 会被 403，
    #    no-referrer 已实测可拿 200；顺带 lazy-load
    body_html = body_html.replace("<img ", '<img referrerpolicy="no-referrer" loading="lazy" ')
    return body_html


def convert_note(pg):
    cur = dict(pg)
    cur["P"] = "../" * cur["depth"]
    body = strip_first_h1(cur["body"])
    body = preprocess_md(body, cur)
    html = convert(body)
    html = rewrite_links(html, cur)
    html = fix_callouts(html)
    html = fix_tasks(html)
    html = fix_imgs(html)
    pg["mermaid"] = "```mermaid" in cur["body"]
    pg["math"] = has_display_math(cur["body"])
    pg["excerpt"] = get_excerpt(cur["body"])
    pg["minutes"] = reading_minutes(cur["body"])
    return html


def convert_fragment(md_text, cur):
    """Shared pipeline for hub README + section overviews."""
    body = strip_first_h1(md_text)
    body = preprocess_md(body, cur)
    html = convert(body)
    html = rewrite_links(html, cur)
    html = fix_callouts(html)
    html = fix_tasks(html)
    html = fix_imgs(html)
    return html


# --------------------------------------------------------------------------
# page shell（与站点模板一致；导航含「我的笔记库」入口）
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
            <li><a href="{P}notes/index.html"><b>{ZONE_NAME}</b><span>Obsidian 知识库在线镜像</span></a></li>
            <li><a href="https://northadb.github.io/agent-learning/lessons/"><b>Agent Learning</b><span>主课 · Python 读懂 harness</span></a></li>
            <li><a href="{P}agent-harness-course/index.html"><b>Agent Harness 架构课程</b><span>逆向 Pi 源码 · 15 课</span></a></li>
            <li><a href="{P}learn-pi/index.html"><b>学习 Pi 导读</b><span>中文导读 · 22 篇</span></a></li>
            <li><a href="{P}web-foundation/COURSE.html"><b>从 HTTP 到实时 Agent Server</b><span>网络通信课</span></a></li>
            <li><a href="{P}rag/index.html"><b>RAG Playground</b><span>手写 RAG 流水线</span></a></li>
          </ul>
        </li>
        <li><a href="{P}about.html">关于</a></li>
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


def shell(P, title, desc, canonical_path, body, page_type="post", mermaid=False,
          math=False, ldjson=None):
    extra = f'\n<link rel="stylesheet" href="{P}{ZONE}/assets/notes.css">'
    ld = f'\n<script type="application/ld+json">\n{ldjson}\n</script>' if ldjson else ""
    mm = f'\n<script src="{P}{ZONE}/assets/mermaid-init.js" defer></script>' if mermaid else ""
    kt = ""
    if math:
        kt = ('\n<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">'
              '\n<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>'
              '\n<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>'
              '\n<script>window.addEventListener("DOMContentLoaded",function(){if(window.renderMathInElement){renderMathInElement(document.querySelector(".prose"),{delimiters:[{left:"$$",right:"$$",display:true},{left:"$",right:"$",display:false}]})}});</script>')
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
<link rel="stylesheet" href="{P}css/style.css">{extra}{ld}{mm}{kt}
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

<script src="{P}js/main.js" defer></script>
</body>
</html>'''


def crumb(P, sec=None):
    parts = [f'<a href="{P}index.html">首页</a><span>/</span>',
             f'<a href="{P}{ZONE}/index.html">{ZONE_NAME}</a>']
    if sec:
        parts.append(f'<span>/</span><a href="{P}{ZONE}/{sec["slug"]}/index.html">{html_mod.escape(sec["title"])}</a>')
    return '<div class="crumbs">' + "".join(parts) + '</div>'


# --------------------------------------------------------------------------
# page builders
# --------------------------------------------------------------------------


def build_note_page(pg, body_html, prev_pg, next_pg):
    sec = pg["section"]
    P = "../" * pg["depth"]
    canonical = f"{ZONE}/{pg['url']}"
    ldjson = json_mod.dumps({
        "@context": "https://schema.org", "@type": "TechArticle",
        "headline": pg["title"], "description": pg["excerpt"],
        "author": {"@type": "Person", "name": "NorthAdb", "url": VAULT_URL},
        "mainEntityOfPage": f"{SITE_URL}/{canonical}",
    }, ensure_ascii=False)

    post_nav = ""
    if prev_pg or next_pg:
        prev_a = '<span></span>'
        if prev_pg:
            prev_a = (f'<a class="prev" href="{zone_href(prev_pg, P)}"><span class="dir">← 上一篇</span>'
                      f'<span class="t">{html_mod.escape(prev_pg["title"])}</span></a>')
        next_a = ""
        if next_pg:
            next_a = (f'<a class="next" href="{zone_href(next_pg, P)}"><span class="dir">下一篇 →</span>'
                      f'<span class="t">{html_mod.escape(next_pg["title"])}</span></a>')
        post_nav = f'<div class="wrap"><nav class="post-nav">{prev_a}{next_a}</nav></div>'

    sec_url = f"{P}{ZONE}/{sec['slug']}/index.html"
    updated = pg["meta"].get("updated") or pg["meta"].get("created")
    meta_date = f'<span class="sep"></span><span>更新于 {html_mod.escape(updated)}</span>' if updated else ""

    tags = (pg["meta"].get("tags") or [])[:4]
    chips = "".join(f'<span class="chip">{html_mod.escape(t)}</span>' for t in tags)
    tags_html = (f'<div class="tags"><span class="chip chip-accent">{html_mod.escape(sec["title"])}</span>{chips}</div>')

    body = f'''  <div class="post-layout">
    <div class="post-main">
      <article>
        <header class="post-hero">
          {crumb(P, sec)}
          <h1>{html_mod.escape(pg["title"])}</h1>
          <p class="post-sub">{html_mod.escape(pg["excerpt"])}</p>
          <div class="post-meta">
            <span class="avatar">N</span>
            <span>{ZONE_NAME}</span><span class="sep"></span>
            <span><a href="{sec_url}">{html_mod.escape(sec["title"])}</a></span><span class="sep"></span>
            <span>阅读约 {pg["minutes"]} 分钟</span>{meta_date}
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
          {tags_html}
          <a class="t-meta" href="{gh_blob(pg['rel'])}" target="_blank" rel="noopener">在 GitHub 查看原文 ↗</a>
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
    return shell(P, f"{pg['title']} · {ZONE_NAME} — NorthAdb 的博客", pg["excerpt"], canonical,
                 body, page_type="post", mermaid=pg.get("mermaid", False),
                 math=pg.get("math", False), ldjson=ldjson)


def build_section_page(sec, sec_pages, P, prev_sec, next_sec):
    canonical = f"{ZONE}/{sec['slug']}/index.html"
    ov = sec_overview.get(sec["slug"])
    overview_html = ""
    if ov:
        cur = dict(rel=f"{sec['dir']}/index.md", section=sec, P=P,
                   headings=headings_of(fm_parse(ov)[1]))
        ov_html = convert_fragment(fm_parse(ov)[1], cur)
        overview_html = f'''  <section class="block wrap" style="padding-top:0;">
    <div class="sec-head"><span class="label">分区导读</span></div>
    <div class="prose prose-narrow">
{ov_html}
    </div>
  </section>'''

    # group pages by their directory inside the section
    groups: dict[str, list] = {}
    for pg in sec_pages:
        rel_dir = Path(pg["rel"]).parent.relative_to(sec["dir"]).as_posix()
        groups.setdefault(rel_dir, []).append(pg)
    order = sorted(groups.keys(), key=lambda d: (d != "", d))

    sections_html = []
    for g in order:
        rows = []
        for i, m in enumerate([p for p in groups[g] if not p.get("asset")], 1):
            href = zone_href(m, P)
            rows.append(f'''      <li>
        <a class="post-row" href="{href}">
          <span class="num">{i:02d}</span>
          <div>
            <h3>{html_mod.escape(m["title"])}</h3>
            <div class="row-meta"><span class="cat">{html_mod.escape(sec["title"])}</span><span class="sep"></span><span>阅读约 {m["minutes"]} 分钟</span></div>
            <p class="row-desc">{html_mod.escape(m["excerpt"])}</p>
          </div>
          <span class="arrow">→</span>
        </a>
      </li>''')
        for m in [p for p in groups[g] if p.get("asset")]:
            rows.append(f'''      <li>
        <a class="post-row" href="{gh_blob(m['rel'])}" target="_blank" rel="noopener">
          <span class="num">PDF</span>
          <div>
            <h3>{html_mod.escape(m["title"])}</h3>
            <div class="row-meta"><span class="cat">PDF 原文件 · 在 GitHub 打开</span></div>
          </div>
          <span class="arrow">↗</span>
        </a>
      </li>''')
        if not rows:
            continue
        label = sec["title"] if g == "" else g + "/"
        sections_html.append(f'''    <div class="ls-group">{html_mod.escape(label)}</div>
    <ul class="post-list">
{"".join(rows)}
    </ul>''')
    listing_html = "\n".join(sections_html)

    nav_cards = []
    if prev_sec:
        nav_cards.append(f'<a class="btn btn-ghost" href="{P}{ZONE}/{prev_sec["slug"]}/index.html">← {html_mod.escape(prev_sec["title"])}</a>')
    if next_sec:
        nav_cards.append(f'<a class="btn btn-ghost" href="{P}{ZONE}/{next_sec["slug"]}/index.html">{html_mod.escape(next_sec["title"])} →</a>')
    nav_row = ('<div class="chapter-nav">' + "".join(nav_cards) + '</div>') if nav_cards else ""

    body = f'''  <section class="hero wrap" style="padding-bottom: 40px;">
    <div class="hero-glow"></div>
    <div class="hero-kicker"><span class="dot"></span> Vault · {html_mod.escape(sec["dir"])}/</div>
    <h1 class="t-h1">{html_mod.escape(sec["title"])}</h1>
    <p class="sub">{html_mod.escape(sec["desc"])}<span class="dim">共 {sum(1 for p in sec_pages if not p.get("asset"))} 篇笔记，来自 <a href="{gh_tree(sec["dir"])}" target="_blank" rel="noopener">{sec["dir"]}/</a>。</span></p>
    <div class="hero-actions">
      <a href="{gh_tree(sec["dir"])}" class="btn btn-ghost">源目录 ↗</a>
      <a href="{P}{ZONE}/index.html" class="btn btn-ghost">返回笔记库 →</a>
    </div>
  </section>

{overview_html}

  <section class="block wrap" style="padding-top: 0;">
{listing_html}
  </section>

  <section class="block wrap">
    {nav_row}
  </section>'''
    desc = f"{sec['desc']} {ZONE_NAME}分区，共 {sum(1 for p in sec_pages if not p.get('asset'))} 篇笔记。"
    return shell(P, f'{sec["title"]} · {ZONE_NAME} — NorthAdb 的博客', desc, canonical,
                 body, page_type="", mermaid=bool(ov and "```mermaid" in ov))


def build_hub(total_pages, total_minutes, total_wl):
    P = "../"
    active_secs = [s for s in SECTIONS if s["slug"] not in SKIP_SECTIONS]
    counts = {}
    for pg in pages:
        if pg.get("section") and not pg.get("asset"):
            counts[pg["section"]["slug"]] = counts.get(pg["section"]["slug"], 0) + 1
    cards = []
    for sec in active_secs:
        n = counts.get(sec["slug"], 0)
        cards.append(f'''      <a class="course-card" href="{sec['slug']}/index.html">
        <span class="c-badge">{html_mod.escape(sec["dir"][:2])}</span>
        <h3>{html_mod.escape(sec["title"])}</h3>
        <p>{html_mod.escape(sec["desc"])}</p>
        <span class="c-link">{n} 篇 · 进入分区 →</span>
      </a>''')
    cards_html = "\n".join(cards)

    about_html = ""
    readme_pg = next((p for p in pages if p["rel"] == "README.md"), None)
    if readme_pg:
        cur = dict(rel="README.md", section=None, P=P, headings=headings_of(readme_pg["body"]))
        b = convert_fragment(readme_pg["body"], cur)
        about_html = f'''  <section class="block wrap">
    <div class="sec-head reveal"><span class="label">关于本库</span></div>
    <div class="prose prose-narrow">
{b}
    </div>
  </section>'''

    body = f'''  <section class="hero wrap">
    <div class="hero-glow"></div>
    <div class="hero-kicker"><span class="dot"></span> Vault · Obsidian · north-my-note</div>
    <h1>我的<em>笔记</em>库</h1>
    <p class="sub">个人 Obsidian 知识库的在线镜像：基于双向链接的笔记系统，覆盖知识领域、项目实践、内容剪藏与岗位情报。
      <span class="dim">同步自 <a href="{VAULT_URL}" target="_blank" rel="noopener">NorthAdb/north-my-note</a>，wikilink 已映射为站内链接。</span></p>
    <div class="hero-actions">
      <a href="domains/index.html" class="btn btn-primary">从知识领域开始</a>
      <a href="{VAULT_URL}" class="btn btn-ghost" target="_blank" rel="noopener">源仓库 ↗</a>
    </div>
    <div class="hero-stats">
      <div><b data-count="{len(active_secs)}">{len(active_secs)}</b>个分区</div>
      <div><b data-count="{total_pages}">{total_pages}</b>篇在线笔记</div>
      <div><b data-count="{total_wl}">{total_wl}</b>条双向链接</div>
      <div><b>0</b>依赖 · 纯静态</div>
    </div>
  </section>

  <section class="block wrap">
    <div class="sec-head reveal">
      <span class="label">知识地图</span>
    </div>
    <div class="course-grid reveal">
{cards_html}
    </div>
  </section>

{about_html}'''
    desc = (f"{ZONE_NAME}：个人 Obsidian 知识库在线镜像，{len(active_secs)} 个分区 "
            f"{total_pages} 篇笔记，覆盖 Agent / RAG / Harness 学习线、项目实践与内容剪藏。")
    return shell(P, f"{ZONE_NAME} — NorthAdb 的博客", desc, f"{ZONE}/index.html",
                 body, page_type="")


# --------------------------------------------------------------------------
# static assets written by the generator
# --------------------------------------------------------------------------

NOTES_CSS = '''/* ============================================================
   我的笔记库 — notes-zone overlay
   Built on the site design tokens (css/style.css). No new colors.
   ============================================================ */

/* wikilinks */
.prose .wl {
  color: var(--accent);
  text-decoration: none;
  border-bottom: 1px dashed var(--accent-border);
}
.prose .wl:hover { color: var(--accent-strong); border-bottom-style: solid; }
.prose .wl.dead {
  color: var(--text-3);
  border-bottom: 1px dashed var(--border);
  cursor: default;
}
.prose .wl.dead:hover { color: var(--text-3); }
.prose .wl.dead small { color: var(--text-3); opacity: .75; font-size: .78em; }

/* Obsidian ==highlight== */
.prose mark {
  background: var(--accent-soft);
  color: var(--text);
  padding: .08em .3em;
  border-radius: 4px;
}

/* Obsidian callouts */
.callout {
  margin: 1.6em 0;
  padding: 13px 18px;
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--r-md);
  background: var(--bg-1);
}
.callout .callout-title {
  margin: 0;
  font-weight: 600;
  font-size: 13.5px;
  letter-spacing: .02em;
  color: var(--text);
}
.callout .callout-title::before { content: "❖ "; color: var(--accent); }
.callout > p { margin: .5em 0 0; }
.callout > *:first-child { margin-top: 0; }
.callout ul, .callout ol { margin: .5em 0 0; }

/* task lists */
.prose li.task { list-style: none; }
.prose li.task .cb {
  display: inline-block;
  width: 13px; height: 13px;
  border: 1.5px solid var(--text-3);
  border-radius: 4px;
  margin-right: 8px;
  vertical-align: -2px;
  position: relative;
}
.prose li.task.done { color: var(--text-3); }
.prose li.task.done .cb {
  background: var(--accent);
  border-color: var(--accent);
}
.prose li.task.done .cb::after {
  content: "✓";
  position: absolute;
  inset: 0;
  color: #0a0a0a;
  font-size: 10px;
  line-height: 12px;
  text-align: center;
  font-weight: 700;
}

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

/* 未入库附件占位（blob 链接的缺失图片 / ![[...]] 嵌入） */
.img-missing {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: .4em 0;
  padding: 8px 12px;
  border: 1px dashed var(--border);
  border-radius: var(--r-sm);
  background: var(--bg-1);
  color: var(--text-3);
  font-size: 13px;
}
.img-missing small { opacity: .75; }

/* KaTeX display blocks can be wide on mobile */
.katex-display { overflow-x: auto; overflow-y: hidden; padding: .3em 0; }

/* section listing: directory group headers */
.ls-group {
  margin: 30px 0 10px;
  font-size: 13px;
  letter-spacing: .06em;
  color: var(--text-3);
  font-family: var(--font-mono);
}
.ls-group:first-child { margin-top: 0; }
.prose-narrow { max-width: var(--prose-w); }
'''

MERMAID_INIT = '''/* 我的笔记库 — mermaid progressive enhancement.
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
      mermaid.render("nm-diagram-" + i, o.src).then(function (res) {
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
  s.src = root + "notes/assets/vendor/mermaid.min.js";
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
    """Insert the 笔记库 entry into the 课件 dropdown and the top nav of an existing page."""
    text = path.read_text(encoding="utf-8")
    m = (re.search(r'<li><a href="((?:\.\./)*)ai-engineer/index\.html">.*?</a></li>', text)
         or re.search(r'<li><a href="((?:\.\./)*)rag/index\.html">.*?</a></li>', text))
    if m:
        P = m.group(1)
        if "<b>我的笔记库</b>" not in text:
            new_item = (f'\n            <li><a href="{P}{ZONE}/index.html"><b>{ZONE_NAME}</b>'
                        f'<span>Obsidian 知识库在线镜像</span></a></li>')
            text = text[:m.end()] + new_item + text[m.end():]
    else:
        # 下拉项已在（如模板自带），从它本身取相对前缀
        m2 = re.search(r'<a href="((?:\.\./)*)notes/index\.html"><b>我的笔记库</b>', text)
        if not m2:
            return "no-anchor"
        P = m2.group(1)
    # 顶部导航与下拉项独立判断：模板自带下拉项不代表顶部导航已插入
    top = f'<a href="{P}notes/index.html">笔记库</a><a href="{P}about.html">关于</a>'
    if top not in text:
        if f'<a href="{P}about.html">关于</a>' not in text:
            return "no-topnav"
        text = text.replace(f'<a href="{P}about.html">关于</a>',
                            f'<a href="{P}notes/index.html">笔记库</a>'
                            f'<a href="{P}about.html">关于</a>', 1)
    path.write_text(text, encoding="utf-8")
    return "ok"


def update_search_json(entries):
    path = SITE / "search.json"
    data = path.read_text(encoding="utf-8").rstrip()
    assert data.startswith("[")
    items = json_mod.loads(data)
    items = [i for i in items if not str(i.get("url", "")).startswith(ZONE + "/")]
    items.extend(entries)
    path.write_text(json_mod.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    ZONE_DIR.mkdir(parents=True, exist_ok=True)
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

    discover()

    # pdf asset rows ride along with their section listing
    for sec in [s for s in SECTIONS if s["slug"] not in SKIP_SECTIONS]:
        root = VAULT / sec["dir"]
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.pdf"), key=lambda p: p.parts):
            rel = p.relative_to(VAULT).as_posix()
            pages.append(dict(rel=rel, section=sec, url=None, title=p.stem,
                              excerpt="", minutes=0, asset=True))

    # ---- convert note pages ----
    note_pages = [p for p in pages if not p.get("asset")]
    for pg in [p for p in note_pages if p["section"] is not None]:
        body_html = convert_note(pg)
        sec_pages = sorted([p for p in note_pages if p["section"] is pg["section"]],
                           key=lambda x: x["rel"])
        idx = sec_pages.index(pg)
        prev_pg = sec_pages[idx - 1] if idx > 0 else None
        next_pg = sec_pages[idx + 1] if idx < len(sec_pages) - 1 else None
        out = ZONE_DIR / pg["url"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_note_page(pg, body_html, prev_pg, next_pg), encoding="utf-8")

    total_wl = sum(1 for pg in note_pages for _ in re.finditer(r"\[\[", pg["body"]))

    # ---- section pages ----
    active_secs = [s for s in SECTIONS if s["slug"] not in SKIP_SECTIONS]
    with_pages = []
    for sec in active_secs:
        has = any(p["section"] is sec for p in pages) or sec_overview.get(sec["slug"])
        if has:
            with_pages.append(sec)
    for i, sec in enumerate(with_pages):
        sec_pages = [p for p in pages if p["section"] is sec]
        html = build_section_page(sec, sec_pages, "../../",
                                  with_pages[i - 1] if i > 0 else None,
                                  with_pages[i + 1] if i < len(with_pages) - 1 else None)
        (ZONE_DIR / sec["slug"]).mkdir(parents=True, exist_ok=True)
        (ZONE_DIR / sec["slug"] / "index.html").write_text(html, encoding="utf-8")

    # ---- hub ----
    total_pages = sum(1 for p in pages if p.get("section") and not p.get("asset"))
    total_minutes = sum(p["minutes"] for p in pages if p.get("section") and not p.get("asset"))
    (ZONE_DIR / "index.html").write_text(
        build_hub(total_pages, total_minutes, total_wl), encoding="utf-8")

    # ---- assets ----
    (ZONE_DIR / "assets" / "notes.css").write_text(NOTES_CSS, encoding="utf-8")
    (ZONE_DIR / "assets" / "mermaid-init.js").write_text(MERMAID_INIT, encoding="utf-8")

    # ---- search.json ----
    entries = [
        {"title": ZONE_NAME, "url": f"{ZONE}/index.html", "category": "笔记库 · Obsidian 在线镜像",
         "excerpt": "个人 Obsidian 知识库在线镜像：知识领域、项目实践、内容剪藏与岗位情报。",
         "type": "note", "featured": True,
         "keywords": "笔记 obsidian vault note wiki 双向链接 剪藏 领域 项目 clippings"},
    ]
    for sec in with_pages:
        n = sum(1 for p in pages if p["section"] is sec and not p.get("asset"))
        entries.append({"title": f'{sec["title"]}（{sec["dir"]}/）',
                        "url": f"{ZONE}/{sec['slug']}/index.html",
                        "category": f"笔记库 · {n} 篇",
                        "excerpt": sec["desc"], "type": "note", "featured": False,
                        "keywords": sec["title"]})
    for pg in pages:
        if pg.get("asset") or pg.get("section") is None or not pg.get("url"):
            continue
        entries.append({"title": pg["title"], "url": f"{ZONE}/{pg['url']}",
                        "category": f'笔记库 · {pg["section"]["title"]}',
                        "excerpt": pg.get("excerpt", ""), "type": "note", "featured": False,
                        "keywords": pg["section"]["title"]})
    update_search_json(entries)

    # ---- sitemap ----
    urls = [f"{ZONE}/index.html"] + [
        f"{ZONE}/{sec['slug']}/index.html" for sec in with_pages
    ] + [f"{ZONE}/{pg['url']}" for pg in pages if not pg.get("asset") and pg.get("url")]
    update_sitemap(urls)

    # ---- nav dropdown in existing pages ----
    nav_targets = [SITE / "index.html", SITE / "learn.html", SITE / "about.html",
                   SITE / "404.html", *sorted((SITE / "posts").glob("*.html"))]
    for pat in ("*.html", "*/*.html", "*/*/*.html"):
        nav_targets += [p for p in sorted((SITE / "ai-engineer").glob(pat)) if p.is_file()]
    for t in nav_targets:
        if t.exists():
            print(f"nav {t.relative_to(SITE)}: {add_nav_item(t)}")

    # ---- report ----
    img_bytes = sum(f.stat().st_size for f in (ZONE_DIR / "assets" / "img").glob("*")) \
        if (ZONE_DIR / "assets" / "img").exists() else 0
    print(f"\nnotes: {total_pages}  sections: {len(with_pages)}  wikilinks: {total_wl}  "
          f"images copied: {len(copied_images)} ({img_bytes / 1e6:.2f} MB)")
    for sec in with_pages:
        n = sum(1 for p in pages if p["section"] is sec and not p.get("asset"))
        print(f"  {sec['slug']:<12} {n:>3} 篇  {sec['dir']}/")
    print(f"\ndead wikilinks: {len(dead_links)}")
    for src, t in dead_links[:12]:
        print(f"  {src} -> [[{t}]]")
    print(f"unresolved embeds: {len(open_embeds)}")
    for src, t in open_embeds[:12]:
        print(f"  {src} -> ![[{t}]]")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
