/*
 * 课程导航组件（assets/nav.js）—— 所有 lessons/ 与 reference/ 页面共用。
 *
 * 引入方式（放在 </body> 前）：
 *   <script src="../assets/nav.js" data-base="../" data-track="lesson"></script>
 *   data-base: 页面所在目录到工作区根的相对路径（lessons/ 与 reference/ 都是一级深，用 ../）
 *   data-track: "lesson" 页面会自动获得底部"上一课/下一课"翻页条；"reference" 只有侧栏
 *
 * 功能：
 *   1. 左侧可折叠目录抽屉：全课程地图（互动课/讲义/实验/图表/速查表），高亮当前页
 *   2. ☰ 按钮（左上角固定）打开目录；ESC 或点击遮罩关闭
 *   3. lesson 页底部自动生成 上一课 ← 目录 → 下一课 翻页条
 */
(function () {
  "use strict";

  var script = document.currentScript;
  // 注意：根目录页面的 data-base 是空字符串 ""（合法值），不能用 || 兜底——
  // 空字符串是假值，会被 "../" 覆盖，导致根页面所有链接跳到工作区上一级。
  var BASE = script && script.dataset.base !== undefined ? script.dataset.base : "../";
  var TRACK = (script && script.dataset.track) || "";

  /* ---------- 课程目录数据（相对工作区根） ---------- */

  var LESSONS = [
    { href: "lessons/0001-course-map.html", short: "课程地图与全景" },
    { href: "lessons/0002-sse-format-lab.html", short: "SSE 格式实验室" },
    { href: "lessons/0003-agent-event-explorer.html", short: "Agent 事件时间线浏览器" },
  ];

  var READINGS = [
    { href: "course/module-0-为什么需要网络通信.html", short: "M0 · 为什么需要网络通信" },
    { href: "course/module-1-异步与HTTP地基.html", short: "M1 · 异步与 HTTP 地基" },
    { href: "course/module-2-流式传输与SSE.html", short: "M2 · 流式传输与 SSE" },
    { href: "course/module-3-WebSocket双向通信.html", short: "M3 · WebSocket 双向通信" },
    { href: "course/module-4-LLM流式与Agent事件.html", short: "M4 · LLM 流式与 Agent 事件" },
    { href: "course/module-5-综合项目与生产化.html", short: "M5 · 综合项目与生产化" },
    { href: "course/module-6-Redis事件总线.html", short: "M6 · Redis 事件总线" },
    { href: "course/module-7-Nginx与部署.html", short: "M7 · Nginx 与部署" },
    { href: "course/appendix-troubleshooting.html", short: "排障附录" },
  ];

  var GROUPS = [
    {
      label: "🎯 课程入口",
      items: [
        ["COURSE.html", "课程总纲（主入口）"],
        ["GLOSSARY.html", "术语表"],
        ["README.html", "工作区导航"],
        ["SSE_WebSocket_FastAPI_完整学习路线.html", "知识底稿（原始路线）"],
      ],
    },
    {
      label: "📖 互动课 lessons",
      items: LESSONS.map(function (l, i) {
        return [l.href, "第 " + (i + 1) + " 课 · " + l.short];
      }),
    },
    {
      label: "🧪 实验区 labs",
      items: [
        ["labs/README.html", "实验索引与环境准备"],
        ["labs/smoke_test.py", "一键回归脚本（源码）"],
        ["labs/a1_async/README.html", "A1 · asyncio 演示"],
        ["labs/v0_hello_api/README.html", "v0 · 第一个 FastAPI"],
        ["labs/v2_streaming/README.html", "v2 · 分块流式"],
        ["labs/v3_sse/README.html", "v3 · SSE 三版本对照"],
        ["labs/v4_websocket/README.html", "v4 · WebSocket 聊天室"],
        ["labs/v5_llm_stream/README.html", "v5 · LLM Token 流"],
        ["labs/v6_agent_events/README.html", "v6 · Agent 事件流"],
        ["labs/v7_agent_server/README.html", "v7 · 毕业实验 ★"],
        ["labs/r1_redis_tasks/README.html", "r1 · 任务表→Hash"],
        ["labs/r2_redis_stream/README.html", "r2 · 事件→Stream"],
        ["labs/r3_redis_fanout/README.html", "r3 · 多进程完全体 ★"],
        ["labs/n1_nginx_proxy/README.html", "n1 · Nginx 事故对照"],
        ["labs/n2_full_stack/README.html", "n2 · 终极拓扑 ★"],
        ["labs/v8_production/README.html", "v8 · 生产化设计"],
      ],
    },
    {
      label: "📚 模块讲义 course",
      items: READINGS.map(function (r) {
        return [r.href, r.short];
      }),
    },
    {
      label: "🗺 图表 diagrams",
      items: [
        ["diagrams/01-agent-server-architecture.html", "01 · 全景架构"],
        ["diagrams/02-sse-lifecycle.html", "02 · SSE 生命周期"],
        ["diagrams/03-websocket-handshake.html", "03 · WebSocket 握手"],
        ["diagrams/04-agent-event-pipeline.html", "04 · Agent 事件管道"],
        ["diagrams/05-agent-server-dual-channel.html", "05 · v7 双通道时序"],
        ["diagrams/06-multi-worker-redis.html", "06 · v8 多 Worker 与 Redis"],
        ["diagrams/07-redis-data-plane.html", "07 · Redis 数据面/控制面"],
        ["diagrams/08-nginx-sse-journey.html", "08 · 流穿 Nginx"],
        ["diagrams/09-final-system.html", "09 · 终极总装"],
      ],
    },
    {
      label: "📎 速查表 reference",
      items: [
        ["reference/sse-cheatsheet.html", "SSE 速查表"],
        ["reference/websocket-cheatsheet.html", "WebSocket 速查表"],
      ],
    },
    {
      label: "🧭 工作区",
      items: [
        ["MISSION.html", "学习使命"],
        ["RESOURCES.html", "资源清单"],
      ],
    },
  ];

  /* ---------- 工具 ---------- */

  function absUrl(href) {
    return new URL(BASE + href, window.location.href);
  }
  function isCurrent(href) {
    try {
      var a = absUrl(href);
      var b = new URL(window.location.href);
      return a.pathname.replace(/\\/g, "/") === b.pathname.replace(/\\/g, "/");
    } catch (e) {
      return false;
    }
  }

  /* ---------- 样式（自包含，避免依赖 course.css 的加载顺序） ---------- */

  var css = [
    ".cn-toggle{position:fixed;top:.8rem;left:.8rem;z-index:1001;padding:.35rem .7rem;",
    "border:1px solid #ddd8c8;border-radius:8px;background:#fffdf5;color:#0f766e;cursor:pointer;",
    "font:600 .82rem/1 'Cascadia Code',Consolas,'Microsoft YaHei',monospace;box-shadow:0 1px 4px rgba(0,0,0,.08)}",
    ".cn-toggle:hover{border-color:#0f766e}",
    "body.cn-open .cn-toggle{opacity:0;pointer-events:none}",
    ".cn-overlay{position:fixed;inset:0;background:rgba(20,20,20,.35);z-index:999;opacity:0;pointer-events:none;transition:opacity .2s}",
    ".cn-sidebar{position:fixed;top:0;left:0;bottom:0;width:min(300px,84vw);z-index:1000;background:#fffdf5;",
    "border-right:1px solid #e4e2d8;box-shadow:4px 0 18px rgba(0,0,0,.10);transform:translateX(-102%);",
    "transition:transform .22s ease;display:flex;flex-direction:column}",
    "body.cn-open .cn-overlay{opacity:1;pointer-events:auto}",
    "body.cn-open .cn-sidebar{transform:translateX(0)}",
    ".cn-head{display:flex;align-items:center;justify-content:space-between;padding:.9rem 1rem .5rem}",
    ".cn-title{font-weight:700;font-size:.9rem;color:#1a1a1a}",
    ".cn-close{border:none;background:none;font-size:1.15rem;cursor:pointer;color:#6b6b6b;padding:.1rem .4rem}",
    ".cn-list{overflow-y:auto;padding:0 .6rem 1rem;flex:1}",
    ".cn-group{margin:.7rem 0 .2rem;font:700 .72rem/1.4 'Cascadia Code',Consolas,'Microsoft YaHei',monospace;",
    "color:#0f766e;letter-spacing:.04em}",
    ".cn-item{display:block;padding:.32rem .6rem;margin:.1rem 0;border-radius:6px;color:#333;",
    "text-decoration:none;font-size:.84rem;line-height:1.45}",
    ".cn-item:hover{background:#f0faf8;text-decoration:none}",
    ".cn-item.cn-here{background:#ccfbf1;color:#0f766e;font-weight:700}",
    ".cn-star{color:#b45309}",
    ".cn-foot{border-top:1px solid #e4e2d8;padding:.6rem 1rem;font-size:.72rem;color:#6b6b6b}",
    ".cn-pager{display:flex;gap:.6rem;align-items:stretch;margin:2.2rem 0 .6rem}",
    ".cn-pager a,.cn-pager button{flex:1;display:flex;flex-direction:column;gap:.15rem;padding:.65rem .9rem;",
    "border:1px solid #e4e2d8;border-radius:10px;background:#fff;cursor:pointer;text-decoration:none;",
    "font-family:inherit;text-align:left}",
    ".cn-pager a:hover,.cn-pager button:hover{border-color:#0f766e}",
    ".cn-pager .cn-dir{font:600 .68rem/1 'Cascadia Code',Consolas,monospace;color:#0f766e;letter-spacing:.08em}",
    ".cn-pager .cn-what{font-size:.9rem;color:#1a1a1a}",
    ".cn-pager .cn-mid{flex:0 0 auto;display:flex;align-items:center}",
    ".cn-pager .cn-mid button{flex:none;align-self:center}",
    ".cn-pager .cn-empty{opacity:.45;pointer-events:none}",
  ].join("");

  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  /* ---------- 侧栏 ---------- */

  var toggle = document.createElement("button");
  toggle.className = "cn-toggle";
  toggle.textContent = "☰ 目录";
  toggle.title = "打开课程目录（Esc 关闭）";

  var overlay = document.createElement("div");
  overlay.className = "cn-overlay";

  var sidebar = document.createElement("aside");
  sidebar.className = "cn-sidebar";
  sidebar.setAttribute("aria-label", "课程目录");

  var head = document.createElement("div");
  head.className = "cn-head";
  head.innerHTML = '<span class="cn-title">📚 课程目录</span>';
  var closeBtn = document.createElement("button");
  closeBtn.className = "cn-close";
  closeBtn.textContent = "✕";
  closeBtn.title = "关闭";
  head.appendChild(closeBtn);

  var list = document.createElement("nav");
  list.className = "cn-list";

  GROUPS.forEach(function (group) {
    var g = document.createElement("div");
    g.className = "cn-group";
    g.textContent = group.label;
    list.appendChild(g);
    group.items.forEach(function (item) {
      var a = document.createElement("a");
      a.className = "cn-item";
      a.href = BASE + item[0];
      a.textContent = item[1];
      if (isCurrent(item[0])) a.classList.add("cn-here");
      if (/毕业实验/.test(item[1])) a.innerHTML = item[1].replace("★", '<span class="cn-star">★</span>');
      list.appendChild(a);
    });
  });

  var foot = document.createElement("div");
  foot.className = "cn-foot";
  foot.textContent = "提示：Esc 或点击遮罩关闭目录；当前页在目录中以绿色高亮。";

  sidebar.appendChild(head);
  sidebar.appendChild(list);
  sidebar.appendChild(foot);

  function open() { document.body.classList.add("cn-open"); }
  function close() { document.body.classList.remove("cn-open"); }
  toggle.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  overlay.addEventListener("click", close);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
  });

  document.body.appendChild(toggle);
  document.body.appendChild(overlay);
  document.body.appendChild(sidebar);

  // 当前页高亮后滚到可见位置
  var here = list.querySelector(".cn-here");
  if (here) here.scrollIntoView({ block: "center" });

  /* ---------- 上一篇 / 下一篇 翻页条（lesson 与 readings 页） ---------- */

  function injectPager(sequence, dirLabels, emptyFirst, emptyLast) {
    var idx = -1;
    sequence.forEach(function (l, i) {
      if (isCurrent(l.href)) idx = i;
    });
    if (idx === -1) return;

    var pager = document.createElement("div");
    pager.className = "cn-pager";

    function cell(dir, item) {
      var a = document.createElement("a");
      a.href = BASE + item.href;
      a.innerHTML =
        '<span class="cn-dir">' + dir + "</span>" +
        '<span class="cn-what">' + item.short + "</span>";
      return a;
    }
    function empty(dir) {
      var s = document.createElement("span");
      s.className = "cn-empty";
      s.style.cssText =
        "flex:1;display:flex;flex-direction:column;gap:.15rem;padding:.65rem .9rem;" +
        "border:1px dashed #e4e2d8;border-radius:10px";
      var label = dir === dirLabels[0] ? emptyFirst : emptyLast;
      s.innerHTML = '<span class="cn-dir">' + dir + "</span><span class='cn-what'>" +
        label + "</span>";
      return s;
    }

    pager.appendChild(idx > 0 ? cell(dirLabels[0], sequence[idx - 1]) : empty(dirLabels[0]));

    var mid = document.createElement("span");
    mid.className = "cn-mid";
    var midBtn = document.createElement("button");
    midBtn.type = "button";
    midBtn.textContent = "☰ 目录";
    midBtn.title = "打开课程目录";
    midBtn.addEventListener("click", open);
    mid.appendChild(midBtn);
    pager.appendChild(mid);

    pager.appendChild(idx < sequence.length - 1
      ? cell(dirLabels[1], sequence[idx + 1])
      : empty(dirLabels[1]));

    var footer = document.querySelector("body > footer");
    if (footer) footer.parentNode.insertBefore(pager, footer);
    else document.body.appendChild(pager);
  }

  if (TRACK === "lesson") {
    injectPager(LESSONS, ["上一课 ←", "下一课 →"], "已经是第一课了", "已经是最后一课了");
  } else if (TRACK === "readings") {
    injectPager(READINGS, ["上一篇 ←", "下一篇 →"], "已经是第一篇了", "已经是最后一篇了");
  }
})();
