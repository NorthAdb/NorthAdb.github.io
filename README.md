# NorthAdb 的博客

Raycast-inspired 的纯静态个人技术博客，托管于 GitHub Pages：面向 AI / Agent / Security 的现代技术博客。

**线上地址**：https://northadb.github.io

## 技术栈

- 纯 HTML + CSS + JavaScript，零依赖、零构建、零框架
- 自建设计系统（Design Tokens）：暗色默认 + 可选亮色主题（`localStorage` 持久化）
- ⌘K 命令面板搜索（`search.json` 按需加载，键盘导航）
- 文章页：TOC（桌面侧栏 + 移动折叠面板）、代码高亮（highlight.js 懒加载）、阅读进度条
- 完整 SEO：canonical、Open Graph、Twitter Card、JSON-LD、`sitemap.xml`、`robots.txt`、`feed.xml`（RSS）

## 目录结构

```
├── index.html              # 首页（Hero / Featured / Latest / Topics / Courses）
├── about.html              # 关于页
├── learn.html              # 课件总览
├── 404.html                # 404 页
├── posts/                  # 文章（每篇一个独立 HTML）
├── css/style.css           # 设计系统（全部样式，设计令牌在文件头部）
├── js/main.js              # 交互（导航/主题/⌘K/TOC/进度条）
├── search.json             # ⌘K 搜索索引
├── sitemap.xml             # 站点地图（116 个 URL）
├── robots.txt / feed.xml   # SEO / RSS
├── agent-harness-course/   # 课件：Agent Harness 架构课程（15 课）
├── learn-pi/               # 课件：学习 Pi 导读（22 篇）
├── rag/                    # 课件：RAG Playground（18 讲）
└── web-foundation/         # 课件：从 HTTP 到实时 Agent Server（8 模块）
```

课程专区（`agent-harness-course/`、`learn-pi/`、`rag/`、`web-foundation/`）自带样式与交互，独立于博客外壳，互不影响。

## 本地预览

```bash
python -m http.server 8000
# 访问 http://localhost:8000
```

## 部署

推送即部署：`git push` → GitHub Actions（`.github/workflows/deploy.yml`）→ GitHub Pages。

## 写作指南

1. 复制 `posts/` 下任意一篇作为模板（头部 meta + `.post-hero` + `.prose` + 标签）
2. 在 `index.html` 的 Latest 列表添加一行，并更新 Featured（如需要）
3. 在 `search.json` 与 `feed.xml`、`sitemap.xml` 中登记新文章
4. `git push` 完成发布

### 可用组件（写进 `.prose` 即可）

- `<div class="callout"><div class="callout-title">Tip</div>内容</div>` — 提示框
- `.prose` 内的 `pre/code` 自动获得深色代码块与语法高亮
- 标准表格、引用块、列表均已在设计系统中定制
