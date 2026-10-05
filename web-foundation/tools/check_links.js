/* 全工作区导航与链接自检（node tools/check_links.js）
 *
 * 检查三件事（完全模拟浏览器行为）：
 *   1. 每个 HTML 页面的 nav.js data-base 是否与其在目录树中的深度一致
 *   2. 用每页自己的 data-base 解析侧栏目录/翻页条的全部目标，验证文件存在
 *   3. 页面正文里所有 href/src（页面相对路径）逐一验证存在
 *
 * 退出码：0 = 全部通过；1 = 有问题（清单见输出）
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");

const navSrc = fs.readFileSync(path.join(ROOT, "assets/nav.js"), "utf8");
const tocPaths = [...new Set([...navSrc.matchAll(/"([^"\n]+\.(?:html|md|py))"/g)].map((m) => m[1]))];

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if ([".venv", "__pycache__", "src", "node_modules"].includes(e.name)) continue;
      walk(p, out);
    } else if (e.name.endsWith(".html") && !e.name.includes(".visual-check")) {
      out.push(p);
    }
  }
  return out;
}

let pagesWithNav = 0;
const baseErrors = [];
const tocErrors = [];
const linkErrors = [];

for (const page of walk(ROOT)) {
  const rel = path.relative(ROOT, page).split(path.sep).join("/");
  const depth = rel.split("/").length - 1;
  const expectedBase = "../".repeat(depth);

  const html = fs.readFileSync(page, "utf8");
  const m = html.match(/<script src="([^"]*?assets\/nav\.js)" data-base="([^"]*)"(?: data-track="([^"]*)")?>/);
  if (!m) {
    if (!rel.startsWith("diagrams/")) baseErrors.push(`${rel}: 缺少 nav.js 引入（diagrams 独立图表页除外）`);
    continue;
  }
  pagesWithNav++;
  const base = m[2];
  if (base !== expectedBase) baseErrors.push(`${rel}: data-base="${base}" 应为 "${expectedBase}"`);

  // 用页面自己的 base 解析目录/翻页全部目标（模拟浏览器点击）
  for (const p of tocPaths) {
    const t = path.resolve(path.dirname(page), base, p);
    if (!fs.existsSync(t)) tocErrors.push(`${rel} [base="${base}"] ${p}`);
  }

  // 页面正文所有 href/src（页面相对路径）
  for (const mm of html.matchAll(/(?:href|src)="([^"#]+)(?:#[^"]*)?"/g)) {
    const href = mm[1];
    if (!href || /^(https?:|mailto:|data:)/.test(href)) continue;
    if (!fs.existsSync(path.resolve(path.dirname(page), href))) {
      linkErrors.push(`${rel} → ${href}`);
    }
  }
}

console.log(`页面总数（接入导航 ${pagesWithNav} + diagrams 独立图表）`);
console.log(`[1] data-base 深度错误：${baseErrors.length} 处`);
baseErrors.forEach((e) => console.log("  !", e));
console.log(`[2] 目录/翻页目标解析失败：${tocErrors.length} 处`);
tocErrors.slice(0, 10).forEach((e) => console.log("  !", e));
console.log(`[3] 页面内 href/src 断链：${linkErrors.length} 处`);
linkErrors.slice(0, 10).forEach((e) => console.log("  !", e));

const total = baseErrors.length + tocErrors.length + linkErrors.length;
console.log(total === 0 ? "\n✔ 全面自检通过" : `\n✘ 共 ${total} 处问题`);
process.exit(total === 0 ? 0 : 1);
