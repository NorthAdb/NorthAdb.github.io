# NorthAdb 的博客

仿 Claude 官网设计语言的纯静态个人博客，托管于 GitHub Pages。

## 技术栈

- 纯 HTML + CSS + JavaScript，零依赖、零构建
- 暗色主题，珊瑚橙点缀（Anthropic 设计语言）
- 响应式布局，支持移动端

## 目录结构

```
├── index.html          # 首页（Hero + 文章卡片 + 关于条）
├── about.html          # 关于页
├── posts/              # 文章（每篇一个独立 HTML）
├── css/style.css       # 全部样式
└── js/main.js          # 交互（导航/进度条/滚动动画）
```

## 本地预览

```bash
# Python
python -m http.server 8000

# 或 Node
npx serve .
```

然后访问 http://localhost:8000

## 部署

推送到 `main` 分支即可，GitHub Actions / Pages 自动发布：

```bash
git add .
git commit -m "update"
git push
```

线上地址：https://NorthAdb.github.io

## 添加新文章

1. 在 `posts/` 下新建 `xxx.html`（参照现有文章结构）
2. 在 `index.html` 的文章卡片区添加对应卡片
3. `git push` 完成发布
