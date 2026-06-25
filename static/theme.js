// 夜间模式：白天 / 夜间主题切换。纯逻辑（resolveInitialTheme / plotlyThemePatch）
// 经 node --test 单测（tests/theme.test.js）；DOM 装配设 data-theme、绑切换按钮、
// 持久化到 localStorage、广播 plotpin:theme-change 事件供图表页联动 Plotly。
// 无 JS 时降级为白天——<head> 内联脚本已先设 data-theme，避免白屏闪烁。
// 主题切换不经过后端，纯客户端状态。

const THEME_KEY = "plotpin-theme";

function resolveInitialTheme(stored, prefersDark) {
  // 存储合法值优先；否则跟随系统 prefers-color-scheme；默认白天。
  if (stored === "light" || stored === "dark") return stored;
  return prefersDark ? "dark" : "light";
}

function plotlyThemePatch(theme, panelN) {
  // 用点路径键（如 "xaxis.gridcolor"）让 Plotly.relayout 合并而非替换整个轴对象，
  // 避免覆盖 build_plotly_spec 设的 tickvals/ticktext。背景透明，由 CSS .panel 承载。
  const dark = theme === "dark";
  const ink = dark ? "#D7E2E2" : "#13212A";
  const grid = dark ? "#20303A" : "#E2E9E9";
  const line = dark ? "#2C3D44" : "#D2DCDC";
  const patch = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font.color": ink,
    "xaxis.gridcolor": grid,
    "xaxis.zerolinecolor": line,
    "xaxis.tickfont.color": ink,
    "xaxis.title.font.color": ink,
  };
  for (let i = 0; i < panelN; i++) {
    const key = i === 0 ? "yaxis" : "yaxis" + (i + 1);
    patch[key + ".gridcolor"] = grid;
    patch[key + ".zerolinecolor"] = line;
    patch[key + ".tickfont.color"] = ink;
    patch[key + ".title.font.color"] = ink;
  }
  return patch;
}

function currentTheme() {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function applyThemeToDoc(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    const icon = btn.querySelector(".theme-toggle-icon");
    const label = btn.querySelector(".theme-toggle-label");
    if (theme === "dark") {
      if (icon) icon.textContent = "☀";
      if (label) label.textContent = "白天";
      btn.setAttribute("aria-label", "切换到白天模式");
    } else {
      if (icon) icon.textContent = "☾";
      if (label) label.textContent = "夜间";
      btn.setAttribute("aria-label", "切换到夜间模式");
    }
  });
  document.dispatchEvent(new CustomEvent("plotpin:theme-change", { detail: { theme } }));
}

function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  try { localStorage.setItem(THEME_KEY, next); } catch (_) {}
  applyThemeToDoc(next);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { resolveInitialTheme, plotlyThemePatch };
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    // 同步按钮文案/图标到当前主题（<head> 内联脚本已先设好 data-theme）。
    applyThemeToDoc(currentTheme());
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.addEventListener("click", toggleTheme);
    });
  });
}
