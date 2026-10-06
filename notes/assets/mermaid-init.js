/* 我的笔记库 — mermaid progressive enhancement.
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
