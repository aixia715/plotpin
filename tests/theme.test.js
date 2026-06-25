// 前端纯逻辑单测（零依赖，node --test 运行）：
//   node --test tests/theme.test.js
// 覆盖夜间模式主题解析与 Plotly 主题补丁，不碰 DOM。
const { test } = require("node:test");
const assert = require("node:assert/strict");

const { resolveInitialTheme, plotlyThemePatch } = require("../static/theme.js");

// ---- resolveInitialTheme：存储优先，其次系统偏好，默认白天 ----
test("resolveInitialTheme: 存储为 light/dark 时优先采用", () => {
  assert.equal(resolveInitialTheme("light", true), "light");
  assert.equal(resolveInitialTheme("dark", false), "dark");
});

test("resolveInitialTheme: 无存储时跟随系统 prefers-color-scheme", () => {
  assert.equal(resolveInitialTheme(null, true), "dark");
  assert.equal(resolveInitialTheme(null, false), "light");
});

test("resolveInitialTheme: 非法存储值回落到系统偏好", () => {
  assert.equal(resolveInitialTheme("blue", true), "dark");
  assert.equal(resolveInitialTheme(undefined, false), "light");
});

test("resolveInitialTheme: 全无信息时默认白天", () => {
  assert.equal(resolveInitialTheme("", false), "light");
  assert.equal(resolveInitialTheme(null, null), "light");
});

// ---- plotlyThemePatch：用点路径补丁，避免覆盖既有轴 tickvals ----
test("plotlyThemePatch: 白天返回浅色配色且透明背景", () => {
  const p = plotlyThemePatch("light", 1);
  assert.equal(p["paper_bgcolor"], "rgba(0,0,0,0)");
  assert.equal(p["plot_bgcolor"], "rgba(0,0,0,0)");
  assert.equal(p["font.color"], "#13212A");
  assert.equal(p["xaxis.gridcolor"], "#E2E9E9");
  assert.equal(p["yaxis.gridcolor"], "#E2E9E9");
});

test("plotlyThemePatch: 夜间返回深色配色", () => {
  const p = plotlyThemePatch("dark", 1);
  assert.equal(p["font.color"], "#D7E2E2");
  assert.equal(p["xaxis.gridcolor"], "#20303A");
  assert.equal(p["yaxis.gridcolor"], "#20303A");
  assert.equal(p["yaxis.title.font.color"], "#D7E2E2");
});

test("plotlyThemePatch: 多面板生成 yaxis / yaxis2 / yaxis3 点路径键", () => {
  const p = plotlyThemePatch("dark", 3);
  assert.ok("yaxis.gridcolor" in p);
  assert.ok("yaxis2.gridcolor" in p);
  assert.ok("yaxis3.gridcolor" in p);
  assert.equal(p["yaxis3.title.font.color"], "#D7E2E2");
});

test("plotlyThemePatch: 不含裸 axis 键，避免 relayout 覆盖 tickvals", () => {
  const p = plotlyThemePatch("light", 2);
  assert.ok(!("xaxis" in p), "不应含裸 xaxis 键");
  assert.ok(!("yaxis" in p), "不应含裸 yaxis 键");
  assert.ok(!("yaxis2" in p), "不应含裸 yaxis2 键");
  for (const k of Object.keys(p)) {
    assert.equal(typeof k, "string");
  }
});
