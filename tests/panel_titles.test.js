// 前端纯逻辑单测（零依赖，node --test 运行）：
//   node --test tests/panel_titles.test.js
// 覆盖标题派生与「自动/手填锁定」状态机，不碰 DOM。
const { test } = require("node:test");
const assert = require("node:assert/strict");

const { filenameStem, autoPanelTitle, computePanelTitles } = require(
  "../static/panel_titles.js"
);

// ---- filenameStem：与后端 app.spec.filename_stem 对齐 ----
test("filenameStem 去扩展名取主名", () => {
  assert.equal(filenameStem("measure.csv"), "measure");
  assert.equal(filenameStem("/tmp/我的 数据.XLSX"), "我的 数据");
  assert.equal(filenameStem("C:\\data\\noext"), "noext");
});

test("filenameStem dotfile 只剥一个前导点，与后端一致", () => {
  assert.equal(filenameStem(".gitignore"), "gitignore");
  assert.equal(filenameStem("..hidden.csv"), "..hidden");
  assert.equal(filenameStem(".gitignore.csv"), ".gitignore");
});

test("filenameStem 缺失/空返回空串（前端用空串表示不预填）", () => {
  assert.equal(filenameStem(null), "");
  assert.equal(filenameStem(""), "");
});

// ---- autoPanelTitle：取分到该面板的首条曲线列名，否则 "Y" ----
test("autoPanelTitle 取该面板第一条曲线列名", () => {
  const assign = { gain: 0, phase: 0, noise: 1 };
  assert.equal(autoPanelTitle(["gain", "phase", "noise"], assign, 0), "gain");
  assert.equal(autoPanelTitle(["gain", "phase", "noise"], assign, 1), "noise");
});

test("autoPanelTitle 按 columns 顺序取首条，不受 assign 键序影响", () => {
  const assign = { a: 1, b: 0, c: 0 };
  assert.equal(autoPanelTitle(["a", "b", "c"], assign, 0), "b");
});

test("autoPanelTitle 空面板与隐藏列兜底", () => {
  const assign = { gain: null, phase: 1 }; // gain 隐藏
  assert.equal(autoPanelTitle(["gain", "phase"], assign, 0), "Y");
  assert.equal(autoPanelTitle(["gain", "phase"], assign, 1), "phase");
});

// ---- computePanelTitles：自动填/手填锁定/加减面板 状态机 ----
const allTo0 = (cols) => Object.fromEntries(cols.map((c) => [c, 0]));

test("初始无 prev：自动按分配预填，未锁定", () => {
  const out = computePanelTitles(["gain"], { gain: 0 }, 1, []);
  assert.deepEqual(out, [{ value: "gain", locked: false }]);
});

test("手填锁定的面板保留原值，不被自动覆盖", () => {
  const prev = [
    { value: "增益 dB", locked: true },
    { value: "phase", locked: false },
  ];
  const out = computePanelTitles(
    ["gain", "phase"], { gain: 0, phase: 1 }, 2, prev
  );
  assert.deepEqual(out, [
    { value: "增益 dB", locked: true },
    { value: "phase", locked: false },
  ]);
});

test("未锁定面板随分配变化重算", () => {
  // panel0 之前自动是 gain，现在把 vcc 分到 panel0 且排在前
  const prev = [{ value: "gain", locked: false }, { value: "Y", locked: false }];
  const out = computePanelTitles(
    ["vcc", "gain"], { vcc: 0, gain: 1 }, 2, prev
  );
  assert.equal(out[0].value, "vcc");
  assert.equal(out[1].value, "gain");
});

test("加面板：新增格按自动规则填（空面板兜底 Y），不锁定", () => {
  const prev = [{ value: "gain", locked: false }];
  const out = computePanelTitles(["gain"], allTo0(["gain"]), 2, prev);
  assert.deepEqual(out, [
    { value: "gain", locked: false },
    { value: "Y", locked: false },
  ]);
});

test("减面板：截断，不暂存被移除格（Q3=B）", () => {
  const prev = [
    { value: "a", locked: true },
    { value: "b", locked: true },
    { value: "c", locked: true },
  ];
  const out = computePanelTitles(["x"], { x: 0 }, 1, prev);
  assert.equal(out.length, 1);
  assert.deepEqual(out[0], { value: "a", locked: true });
});

test("删空解锁的面板：下次重算用表头回填（Q2）", () => {
  const prev = [{ value: "", locked: false }];
  const out = computePanelTitles(["gain"], { gain: 0 }, 1, prev);
  assert.deepEqual(out, [{ value: "gain", locked: false }]);
});
