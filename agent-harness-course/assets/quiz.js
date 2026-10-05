/* 课程共用测验组件：在页面内放 <div class="quiz" data-quiz='...JSON...'></div>
   JSON: { "title": "...", "items": [ { "q": "...", "options": ["A","B","C"], "answer": 1, "why": "..." } ] }
   answer 永远指向 options 的原始下标；渲染时打乱显示顺序，按内容判定；反馈只显示对错与解释。 */
(function () {
  function shuffle(arr) {
    const a = arr.map((value, index) => ({ v: value, i: index }));
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
  document.querySelectorAll(".quiz[data-quiz]").forEach((root) => {
    let data;
    try { data = JSON.parse(root.getAttribute("data-quiz")); } catch (e) { return; }
    const title = data.title || "检索练习";
    let html = "<h3>✎ " + title + "</h3>";
    data.items.forEach((item, qi) => {
      const opts = shuffle(item.options);
      html += '<fieldset data-qi="' + qi + '"><legend>' + (qi + 1) + ". " + item.q + "</legend>";
      opts.forEach((opt) => {
        html += '<label><input type="radio" name="q' + qi + '" value="' + opt.i + '"> ' + opt.v + "</label>";
      });
      html += "</fieldset>";
    });
    html += '<button class="btn" type="button">检查</button><div class="result"></div>';
    root.innerHTML = html;
    root.querySelector(".btn").addEventListener("click", () => {
      let right = 0;
      const whyLines = [];
      data.items.forEach((item, qi) => {
        const sel = root.querySelector('input[name="q' + qi + '"]:checked');
        const ok = sel && Number(sel.value) === item.answer;
        if (ok) right++;
        if (item.why) whyLines.push((ok ? "✓ " : "✗ ") + item.why);
      });
      const res = root.querySelector(".result");
      res.innerHTML =
        '<span class="' + (right === data.items.length ? "ok" : "bad") + '">' +
        right + " / " + data.items.length + "</span>" +
        (whyLines.length ? '<div class="why">' + whyLines.join("<br>") + "</div>" : "");
    });
  });
})();
