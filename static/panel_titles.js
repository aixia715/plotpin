// 纯逻辑：标题派生 + 面板标题「自动/手填锁定」状态机。不碰 DOM。
// 浏览器里作为普通脚本提供全局函数；node 下经 module.exports 供单测。
// 必须在 builder.js 之前加载（templates/index.html）。

function filenameStem(name) {
  // 与后端 app.spec.filename_stem 对齐：去扩展名取主名；无扩展名的
  // dotfile（.gitignore）只剥一个前导点；有扩展名的（..hidden.csv）原样保留。
  // 差异：前端缺失/空返回空串（表示「不预填」），后端兜底 "chart"。
  if (!name) return "";
  const base = name.split("/").pop().split("\\").pop();
  const dot = base.lastIndexOf(".");
  if (dot === 0) return base.slice(1) || "";
  if (dot > 0) return base.slice(0, dot) || "";
  return base || "";
}

function autoPanelTitle(columns, assign, panelIndex) {
  // 取按 columns 顺序、首条分配到该面板的曲线列名；无则兜底 "Y"。
  // 与后端 app.spec.auto_panel_y_title 同义。
  for (const col of columns) {
    if (assign[col] === panelIndex) return col;
  }
  return "Y";
}

function computePanelTitles(columns, assign, panelCount, prev) {
  // 依据当前 columns/assign 重算每个面板标题，并保留手填锁定的格子。
  //  - 已锁定（手填过）→ 原值原样保留，自动逻辑不碰；
  //  - 未锁定（自动 / 删空解锁）→ 用 autoPanelTitle 重算；
  //  - 新增面板（超出 prev 长度）→ 自动填、未锁定（减面板则自然截断，不暂存）。
  const out = [];
  for (let i = 0; i < panelCount; i++) {
    const p = prev[i];
    if (p && p.locked) {
      out.push({ value: p.value, locked: true });
    } else {
      out.push({ value: autoPanelTitle(columns, assign, i), locked: false });
    }
  }
  return out;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { filenameStem, autoPanelTitle, computePanelTitles };
}
