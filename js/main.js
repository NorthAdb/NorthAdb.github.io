/* ============================================================
   NorthAdb Blog — interactions
   Vanilla JS, zero dependencies. Loaded with defer.
   Optional per-page hooks via data attributes:
     <body data-root="../">          path prefix for search.json
     <body data-page="post">         enables TOC + code highlight
   ============================================================ */

(function () {
  "use strict";

  var root = document.body.getAttribute("data-root") || "";
  var page = document.body.getAttribute("data-page") || "";

  /* ---- theme (dark default, persisted) ---- */
  var themeBtn = document.getElementById("themeToggle");
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem("theme", t); } catch (e) {}
  }
  try {
    var saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") applyTheme(saved);
  } catch (e) {}
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
      applyTheme(cur === "light" ? "dark" : "light");
    });
  }

  /* ---- mobile nav ---- */
  var burger = document.getElementById("navBurger");
  var navLinks = document.getElementById("navLinks");
  if (burger && navLinks) {
    burger.addEventListener("click", function () {
      navLinks.classList.toggle("open");
    });
    navLinks.addEventListener("click", function (e) {
      if (e.target.closest("a")) navLinks.classList.remove("open");
      var drop = e.target.closest(".nav-drop > a");
      if (drop && window.matchMedia("(max-width: 820px)").matches) {
        e.preventDefault();
        drop.parentElement.classList.toggle("open");
      }
    });
  }

  /* ---- reveal on scroll ---- */
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("in"); });
  }

  /* ---- reading progress (article pages) ---- */
  var progress = document.getElementById("progress");
  if (progress) {
    var updateProgress = function () {
      var doc = document.documentElement;
      var total = doc.scrollHeight - doc.clientHeight;
      progress.style.width = (total > 0 ? (window.scrollY / total) * 100 : 0) + "%";
    };
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", updateProgress);
    updateProgress();
  }

  /* ---- back to top ---- */
  var toTop = document.getElementById("toTop");
  if (toTop) {
    window.addEventListener("scroll", function () {
      toTop.classList.toggle("show", window.scrollY > 480);
    }, { passive: true });
    toTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  /* ---- TOC: build from h2/h3, scrollspy ---- */
  var tocHosts = document.querySelectorAll(".toc-build");
  var prose = document.querySelector(".prose");
  if (tocHosts.length && prose) {
    var heads = prose.querySelectorAll("h2, h3");
    if (heads.length >= 2) {
      heads.forEach(function (h, i) {
        if (!h.id) h.id = "h-" + i;
      });
      tocHosts.forEach(function (host) {
        var ul = document.createElement("ul");
        heads.forEach(function (h) {
          var li = document.createElement("li");
          li.className = h.tagName === "H2" ? "toc-h2" : "toc-h3";
          var a = document.createElement("a");
          a.href = "#" + h.id;
          a.textContent = h.textContent;
          li.appendChild(a);
          ul.appendChild(li);
        });
        host.appendChild(ul);
      });

      var links = document.querySelectorAll(".toc-build a");
      var spy = function () {
        var y = window.scrollY + 120;
        var current = -1;
        heads.forEach(function (h, i) {
          if (h.offsetTop <= y) current = i;
        });
        links.forEach(function (a, i) {
          a.classList.toggle("current", i === current);
        });
      };
      window.addEventListener("scroll", spy, { passive: true });
      spy();
    } else {
      document.querySelectorAll(".toc, .toc-mobile").forEach(function (el) {
        el.style.display = "none";
      });
    }
  }

  /* ---- code highlight: load hljs only when code exists ---- */
  if (page === "post" && prose && prose.querySelector("pre code")) {
    var s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js";
    s.defer = true;
    s.onload = function () {
      try {
        window.hljs.configure({ cssSelector: ".prose pre code" });
        window.hljs.highlightAll();
      } catch (e) {}
    };
    document.head.appendChild(s);
  }

  /* ---- command palette (⌘K / Ctrl+K) ---- */
  var overlay = document.getElementById("cmdk");
  if (overlay) {
    var input = overlay.querySelector(".cmdk-input");
    var list = overlay.querySelector(".cmdk-list");
    var items = [];        // flattened searchable entries
    var flat = [];         // currently rendered result elements
    var rendered = [];     // data behind the currently rendered rows
    var selected = 0;
    var loaded = false;

    var ICONS = {
      post:  ["✦", "文章"],
      page:  ["◈", "页面"],
      course:["▤", "课件"],
      topic: ["◇", "方向"]
    };

    function defaultEntries(data) {
      return data.filter(function (d) { return d.featured; })
        .concat(data.filter(function (d) { return !d.featured; }))
        .slice(0, 9);
    }

    function render(entries, q) {
      rendered = entries;
      list.innerHTML = "";
      flat = [];
      selected = 0;
      if (!entries.length) {
        var empty = document.createElement("li");
        empty.className = "cmdk-empty";
        empty.textContent = q ? "没有找到「" + q + "」相关内容" : "索引加载失败，请重试";
        list.appendChild(empty);
        return;
      }
      var lastGroup = null;
      entries.forEach(function (d) {
        var icon = ICONS[d.type] || ICONS.page;
        if (d.type !== lastGroup) {
          lastGroup = d.type;
          var g = document.createElement("li");
          g.className = "cmdk-group";
          g.textContent = icon[1];
          list.appendChild(g);
        }
        var li = document.createElement("li");
        li.className = "cmdk-item";
        li.innerHTML =
          '<span class="ck">' + icon[0] + "</span>" +
          '<div><b></b><span class="sub"></span></div>' +
          '<span class="go">↵</span>';
        li.querySelector("b").textContent = d.title;
        li.querySelector(".sub").textContent = d.category || d.excerpt || "";
        li.addEventListener("click", function () { go(d); });
        list.appendChild(li);
        flat.push(li);
      });
      select(0);
    }

    function select(i) {
      selected = i;
      flat.forEach(function (el, j) {
        el.classList.toggle("selected", j === i);
        if (j === i) el.scrollIntoView({ block: "nearest" });
      });
    }

    function go(d) {
      close();
      window.location.href = root + d.url;
    }

    function score(d, q) {
      var t = d.title.toLowerCase(), c = (d.category || "").toLowerCase();
      var k = (d.keywords || "").toLowerCase();
      if (t.indexOf(q) === 0) return 100;
      if (t.indexOf(q) !== -1) return 80;
      if (c.indexOf(q) !== -1) return 60;
      if (k.indexOf(q) !== -1) return 40;
      return 0;
    }

    function search(q) {
      if (!loaded || !q) { render(loaded ? defaultEntries(items) : [], q); return; }
      var ql = q.toLowerCase();
      var hits = items.map(function (d) { return { d: d, s: score(d, ql) }; })
        .filter(function (x) { return x.s > 0; })
        .sort(function (a, b) { return b.s - a.s; })
        .map(function (x) { return x.d; });
      render(hits, q);
    }

    function open() {
      overlay.classList.add("open");
      document.body.style.overflow = "hidden";
      if (!loaded) {
        fetch(root + "search.json")
          .then(function (r) { return r.json(); })
          .then(function (data) { loaded = true; items = data; search(input.value); })
          .catch(function () { render([], input.value); });
      }
      input.value = "";
      search("");
      input.focus();
    }
    function close() {
      overlay.classList.remove("open");
      document.body.style.overflow = "";
    }

    document.querySelectorAll("[data-cmdk]").forEach(function (btn) {
      btn.addEventListener("click", open);
    });
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) close();
    });
    input.addEventListener("input", function () { search(input.value.trim()); });
    document.addEventListener("keydown", function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        overlay.classList.contains("open") ? close() : open();
        return;
      }
      if (!overlay.classList.contains("open")) return;
      if (e.key === "Escape") { close(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); select(Math.min(selected + 1, flat.length - 1)); }
      else if (e.key === "ArrowUp") { e.preventDefault(); select(Math.max(selected - 1, 0)); }
      else if (e.key === "Enter" && rendered[selected]) { go(rendered[selected]); }
    });
  }

  /* ---- footer year ---- */
  var yearEls = document.querySelectorAll("[data-year]");
  var now = new Date().getFullYear();
  yearEls.forEach(function (el) { el.textContent = now; });
})();
