# 对数轴自动剔除 ≤0 值并警告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 本计划已对齐 issue 11 之后的**多面板 `ChartSpec` 架构**（`app/spec.py`）。

**Goal:** 含 ≤0 值的 CSV 在对数坐标下不再被拒绝，而是自动剔除对数轴上的 ≤0 点照常出图，并在图表页弹约 3 秒警告 toast。

**Architecture:** 纯逻辑层 `app/spec.py` 新增 `apply_log_filter(parsed, spec)` 完成剔除与"全 ≤0 报错"，并报告命中了哪条轴；`validate_spec` 去掉"含 ≤0 即拒绝"、改为末尾调 `apply_log_filter` 触发全 ≤0 报错。渲染层两个渲染器内部统一调用它，保证三个入口（上传校验、交互页、PNG/SVG）一致；Plotly spec 顺带带出警告文案，图表页据此渲染 toast。警告实时计算、不持久化，存储 schema 不变。

**Tech Stack:** FastAPI + Jinja2 + 原生 JS + Plotly.js；matplotlib（静态出图）；pytest（TDD）。

## Global Constraints

- 依赖方向只能从外往里指：路由 → 数据/逻辑；逻辑层内部 `rendering → spec → parsing → eng_notation`。不得反向依赖。`apply_log_filter` 因依赖 `ChartSpec`，必须放在 `app/spec.py`，**不可**放 `parsing.py`。
- 新业务逻辑优先放纯逻辑层并配单测，保持 `app/main.py` 薄。
- 改动遵循 TDD：先写失败测试再实现。纯逻辑层是测试投入重点。
- 测试在 `tests/`，用 `python -m pytest` 运行。
- 改前端（`templates/`、`static/`）做视觉时启用 `frontend-design` skill（不可用则按其原则手工实现，不阻塞）。
- 警告文案逐字固定（多面板聚合，不逐面板列举）：
  - 仅 X：`对数 X 轴包含 ≤0 的值，已自动忽略`
  - 仅 Y：`对数 Y 轴包含 ≤0 的值，已自动忽略`
  - X 和 Y：`对数 X 轴和 Y 轴包含 ≤0 的值，已自动忽略`
  - 无剔除：空串 `""`
- 全 ≤0 报错文案：`X 轴所有值 ≤0，无法使用对数坐标` / `面板 {i+1} 所有值 ≤0，无法使用对数坐标`。

---

### Task 1: 纯逻辑层 `apply_log_filter` + `LogFilterReport`，改 `validate_spec`

**Files:**
- Modify: `app/spec.py`（新增 `LogFilterReport`、`apply_log_filter`；删除 `validate_spec` 中 ≤0 拒绝逻辑、末尾追加 `apply_log_filter` 调用）
- Test: `tests/test_spec.py`（迁移 2 条语义翻转的测试；新增 `apply_log_filter` 测试）

**Interfaces:**
- Consumes: 现有 `ChartSpec`（`x_log: bool`、`panels: list[PanelSpec]`、`assign: dict[str, int | None]`）、`PanelSpec`（`y_log: bool`）、`ParsedCSV`（`x_label`、`x`、`y_labels`、`ys`）、`CSVParseError`。
- Produces:
  - `class LogFilterReport` —— `@dataclass`，字段 `x_dropped: bool = False`、`y_dropped: bool = False`。
  - `apply_log_filter(parsed: ParsedCSV, spec: ChartSpec) -> tuple[ParsedCSV, LogFilterReport]`，语义见 Step 3。
  - `validate_spec` 行为：结构非法或任一对数轴**全** ≤0 → `raise CSVParseError`；部分 ≤0 不再抛。

- [ ] **Step 1: 迁移旧测试 + 写新失败测试**

在 `tests/test_spec.py`：

(a) 把 `test_validate_log_panel_with_nonpositive`（约 77-82 行）整体替换为：

```python
def test_apply_log_filter_y_panel_gaps_nonpositive():
    from app.spec import apply_log_filter
    # phase 含 -1，归到对数面板 0 → 现在剔除而非报错
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)],
                     {"gain": 0, "phase": 0, "noise": None})
    out, report = apply_log_filter(spec=spec, parsed=_parsed())
    # phase 第 0 个值 -1 被置空成缺口；gain 不变
    assert out.ys[_parsed().y_labels.index("phase")][0] is None
    assert out.ys[_parsed().y_labels.index("gain")] == [1.0, 2.0, 3.0]
    assert report.y_dropped is True
    assert report.x_dropped is False
```

(b) 把 `test_validate_x_log_nonpositive`（约 92-96 行）整体替换为：

```python
def test_apply_log_filter_x_drops_nonpositive_rows():
    from app.spec import apply_log_filter
    parsed = ParsedCSV("f", [0.0, 1.0, 2.0], ["gain"], [[5.0, 2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    out, report = apply_log_filter(parsed, spec)
    assert out.x == [1.0, 2.0]
    assert out.ys == [[2.0, 3.0]]       # y 同步对齐删除
    assert report.x_dropped is True
    assert report.y_dropped is False
```

(c) 在文件末尾追加：

```python
def test_apply_log_filter_no_log_unchanged():
    from app.spec import apply_log_filter
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, False)],
                     {"gain": 0, "phase": 0, "noise": 0})
    out, report = apply_log_filter(_parsed(), spec)
    assert out.ys == _parsed().ys
    assert report.x_dropped is False and report.y_dropped is False


def test_apply_log_filter_nonlog_panel_keeps_nonpositive():
    from app.spec import apply_log_filter
    # phase(-1) 在非 log 面板 1 → 保留；面板 0 为 log 只含全正 gain
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("a", True, True), PanelSpec("b", True, False)],
                     {"gain": 0, "phase": 1, "noise": None})
    out, report = apply_log_filter(_parsed(), spec)
    assert out.ys[_parsed().y_labels.index("phase")] == [-1.0, 0.5, 2.0]
    assert report.y_dropped is False


def test_apply_log_filter_all_positive_no_drop():
    from app.spec import apply_log_filter
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, True)],
                     {"gain": 0, "phase": None, "noise": 0})
    out, report = apply_log_filter(_parsed(), spec)
    assert report.x_dropped is False and report.y_dropped is False


def test_apply_log_filter_x_all_nonpositive_raises():
    from app.spec import apply_log_filter
    parsed = ParsedCSV("f", [0.0, -1.0], ["gain"], [[2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    with pytest.raises(CSVParseError):
        apply_log_filter(parsed, spec)


def test_apply_log_filter_panel_all_nonpositive_raises():
    from app.spec import apply_log_filter
    parsed = ParsedCSV("f", [1.0, 2.0], ["gain"], [[0.0, -1.0]])
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)], {"gain": 0})
    with pytest.raises(CSVParseError):
        apply_log_filter(parsed, spec)


def test_apply_log_filter_panel_one_col_allnonpositive_ok():
    from app.spec import apply_log_filter
    # gain 全 ≤0 但同面板 noise 有正数 → 不报错，gain 整列置空
    parsed = ParsedCSV("f", [1.0, 2.0], ["gain", "noise"], [[0.0, -1.0], [10.0, 20.0]])
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)],
                     {"gain": 0, "noise": 0})
    out, report = apply_log_filter(parsed, spec)
    assert out.ys[0] == [None, None]
    assert out.ys[1] == [10.0, 20.0]
    assert report.y_dropped is True


def test_validate_spec_partial_nonpositive_now_ok():
    from app.spec import validate_spec
    # x_log 含 0 但有正数剩余 → validate_spec 不再抛
    parsed = ParsedCSV("f", [0.0, 1.0, 2.0], ["gain"], [[5.0, 2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    validate_spec(spec, parsed)  # 不抛异常


def test_validate_spec_all_nonpositive_still_raises():
    from app.spec import validate_spec
    parsed = ParsedCSV("f", [0.0, -1.0], ["gain"], [[2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    with pytest.raises(CSVParseError):
        validate_spec(spec, parsed)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_spec.py -v`
Expected: 新增/迁移测试 FAIL（`ImportError: cannot import name 'apply_log_filter'`）。

- [ ] **Step 3: 实现 `app/spec.py` 改动**

在 `app/spec.py` 顶部 `from dataclasses import asdict, dataclass` 保持不变。在 `validate_spec` 定义**之前**新增：

```python
@dataclass
class LogFilterReport:
    x_dropped: bool = False
    y_dropped: bool = False


def apply_log_filter(
    parsed: ParsedCSV, spec: ChartSpec
) -> tuple[ParsedCSV, LogFilterReport]:
    x = list(parsed.x)
    ys = [list(col) for col in parsed.ys]
    x_dropped = False
    y_dropped = False

    # 共享 X 对数轴：删除 x ≤ 0 的整行
    if spec.x_log:
        keep = [i for i, v in enumerate(x) if v is not None and v > 0]
        if len(keep) != len(x):
            x_dropped = True
        if not keep:
            raise CSVParseError("X 轴所有值 ≤0，无法使用对数坐标")
        x = [x[i] for i in keep]
        ys = [[col[i] for i in keep] for col in ys]

    # 每个对数面板：分配到它的列里 ≤0 的点置 None（缺口）
    col_index = {label: i for i, label in enumerate(parsed.y_labels)}
    for pi, panel in enumerate(spec.panels):
        if not panel.y_log:
            continue
        panel_cols = [c for c, idx in spec.assign.items() if idx == pi]
        any_positive = False
        for c in panel_cols:
            col = ys[col_index[c]]
            for j, v in enumerate(col):
                if v is None:
                    continue
                if v <= 0:
                    col[j] = None
                    y_dropped = True
                else:
                    any_positive = True
        if panel_cols and not any_positive:
            raise CSVParseError(f"面板 {pi + 1} 所有值 ≤0，无法使用对数坐标")

    filtered = ParsedCSV(parsed.x_label, x, list(parsed.y_labels), ys)
    return filtered, LogFilterReport(x_dropped, y_dropped)
```

然后改 `validate_spec`：**删除**末尾的 ≤0 拒绝段落（从 `if spec.x_log and any(v <= 0 for v in parsed.x):` 一直到函数结尾的 `for pi, panel ...` 那段，即现有约 66-74 行），替换为对 `apply_log_filter` 的调用：

```python
    for pi in range(len(spec.panels)):
        if not any(idx == pi for idx in spec.assign.values()):
            raise CSVParseError(f"面板 {pi + 1} 没有分配任何曲线")
    # 对数轴 ≤0：部分剔除不报错，仅"全 ≤0"在此触发拒绝
    apply_log_filter(parsed, spec)
```

（即保留结构校验，把原 66-74 行的两段 ≤0 检查整体换成最后这一行 `apply_log_filter(parsed, spec)`。）

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_spec.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add app/spec.py tests/test_spec.py
git commit -m "feat(spec): apply_log_filter 剔除对数轴 ≤0 值并报告，validate_spec 仅全≤0 拒绝 (issue 18)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 渲染层接入过滤 + Plotly spec 带警告文案

**Files:**
- Modify: `app/rendering.py`（import 增补；`_ticks` 忽略 None；新增 `_log_warning_text`；`build_plotly_spec`/`render_static` 调过滤）
- Test: `tests/test_rendering.py`（追加测试）

**Interfaces:**
- Consumes: `app.spec.apply_log_filter`、`LogFilterReport`、`ChartSpec`；`ParsedCSV`；现有 `log_ticks`/`nice_ticks`/`format_eng`/`format_plain`。
- Produces:
  - `_log_warning_text(report: LogFilterReport) -> str`，按 Global Constraints 文案表返回，无剔除返回 `""`。
  - `build_plotly_spec(parsed, spec)` 返回 dict 新增键 `"warning": str`。
  - `build_plotly_spec`/`render_static` 内部先对 `parsed` 做 `apply_log_filter`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_rendering.py` 末尾追加（顶部已 `from app.parsing import ParsedCSV`、`from app.spec import ChartSpec, PanelSpec`）：

```python
def test_ticks_ignore_none():
    from app.rendering import _ticks
    ticks = _ticks([None, 1.0, 10.0, 100.0], True)
    assert ticks
    assert all(t > 0 for t in ticks)


def test_build_spec_y_log_nulls_nonpositive_and_warns():
    from app.rendering import build_plotly_spec
    parsed = ParsedCSV("x", [1.0, 10.0, 100.0], ["gain"], [[0.0, 5.0, 50.0]])
    spec = ChartSpec("T", "X", False, False, [PanelSpec("Y", False, True)], {"gain": 0})
    out = build_plotly_spec(parsed, spec)
    assert out["data"][0]["y"][0] is None
    assert out["data"][0]["y"][1:] == [5.0, 50.0]
    assert out["data"][0]["customdata"][0][1] is None   # None 点 customdata 不崩
    assert out["warning"] == "对数 Y 轴包含 ≤0 的值，已自动忽略"


def test_build_spec_x_log_drops_rows_and_warns():
    from app.rendering import build_plotly_spec
    parsed = ParsedCSV("x", [0.0, 10.0, 100.0], ["gain"], [[1.0, 2.0, 3.0]])
    spec = ChartSpec("T", "X", False, True, [PanelSpec("Y", False, False)], {"gain": 0})
    out = build_plotly_spec(parsed, spec)
    assert out["data"][0]["x"] == [10.0, 100.0]
    assert out["data"][0]["y"] == [2.0, 3.0]
    assert out["warning"] == "对数 X 轴包含 ≤0 的值，已自动忽略"


def test_build_spec_both_axes_warning_text():
    from app.rendering import build_plotly_spec
    parsed = ParsedCSV("x", [0.0, 10.0], ["gain"], [[-1.0, 20.0]])
    spec = ChartSpec("T", "X", False, True, [PanelSpec("Y", False, True)], {"gain": 0})
    out = build_plotly_spec(parsed, spec)
    assert out["warning"] == "对数 X 轴和 Y 轴包含 ≤0 的值，已自动忽略"


def test_build_spec_no_warning_when_clean():
    from app.rendering import build_plotly_spec
    out = build_plotly_spec(_sample(), _one_panel(x_log=True, y_log=True))
    assert out["warning"] == ""


def test_render_static_with_gaps_does_not_crash():
    from app.rendering import render_static
    parsed = ParsedCSV("x", [1.0, 10.0, 100.0], ["gain"], [[0.0, 5.0, 50.0]])
    spec = ChartSpec("T", "X", False, False, [PanelSpec("Y", False, True)], {"gain": 0})
    data = render_static(parsed, spec, "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: 运行新测试，确认失败**

Run: `python -m pytest tests/test_rendering.py -v`
Expected: 新增测试 FAIL（`out["warning"]` KeyError；或 `_ticks` 对 None 报 `TypeError`）。

- [ ] **Step 3: 实现渲染层改动**

在 `app/rendering.py`：把第 13 行 import 改为：

```python
from app.spec import ChartSpec, LogFilterReport, apply_log_filter  # noqa: E402
```

把 `_ticks` 改为：

```python
def _ticks(values, use_log: bool):
    vals = [v for v in values if v is not None]
    lo, hi = min(vals), max(vals)
    return log_ticks(lo, hi) if use_log else nice_ticks(lo, hi)
```

在 `_ticks` 之后新增：

```python
def _log_warning_text(report: LogFilterReport) -> str:
    if report.x_dropped and report.y_dropped:
        return "对数 X 轴和 Y 轴包含 ≤0 的值，已自动忽略"
    if report.x_dropped:
        return "对数 X 轴包含 ≤0 的值，已自动忽略"
    if report.y_dropped:
        return "对数 Y 轴包含 ≤0 的值，已自动忽略"
    return ""
```

把 `render_static` 开头（`col_values = ...` 之前）插入过滤，并在 `ax.plot` 处把 None 转 NaN：

```python
def render_static(parsed, spec, fmt):
    parsed, _report = apply_log_filter(parsed, spec)
    col_values = dict(zip(parsed.y_labels, parsed.ys))
    n = len(spec.panels)
    fig, axes = plt.subplots(n, 1, figsize=(8, max(3, 2.6 * n)), sharex=True, squeeze=False)
    axes = [row[0] for row in axes]
    try:
        for idx, panel in enumerate(spec.panels):
            ax = axes[idx]
            for col, i in spec.assign.items():
                if i == idx:
                    ys_plot = [float("nan") if v is None else v for v in col_values[col]]
                    ax.plot(parsed.x, ys_plot, label=col)
```

（`render_static` 其余部分保持不变。）

把 `build_plotly_spec` 开头插入过滤、`customdata` 保护、末尾带 warning：

```python
def build_plotly_spec(parsed, spec):
    parsed, report = apply_log_filter(parsed, spec)
    xf = _formatter(spec.x_eng)
    col_values = dict(zip(parsed.y_labels, parsed.ys))
    n = len(spec.panels)
    domains = _panel_domains(n)

    traces = []
    for col, idx in spec.assign.items():
        if idx is None:
            continue
        panel = spec.panels[idx]
        yf = _formatter(panel.y_eng)
        ys = col_values[col]
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": col,
            "x": parsed.x,
            "y": ys,
            "yaxis": _yref(idx),
            "customdata": [
                [xf(xv), (yf(yv) if yv is not None else None)]
                for xv, yv in zip(parsed.x, ys)
            ],
            "hovertemplate": (
                f"{spec.x_title}: %{{customdata[0]}}<br>"
                f"{panel.y_title}: %{{customdata[1]}}<extra>%{{fullData.name}}</extra>"
            ),
        })

    x_ticks = _ticks(parsed.x, spec.x_log)
    bottom_ref = _yref(n - 1)
    xaxis = {
        "title": {"text": spec.x_title},
        "tickvals": x_ticks,
        "ticktext": [xf(t) for t in x_ticks],
        "anchor": bottom_ref,
    }
    if spec.x_log:
        xaxis["type"] = "log"

    layout = {"title": {"text": spec.title}, "xaxis": xaxis}
    for idx, panel in enumerate(spec.panels):
        yf = _formatter(panel.y_eng)
        panel_cols = [col_values[c] for c, i in spec.assign.items() if i == idx]
        flat = [v for ys in panel_cols for v in ys] or [0.0, 1.0]
        y_ticks = _ticks(flat, panel.y_log)
        ax = {
            "title": {"text": panel.y_title},
            "tickvals": y_ticks,
            "ticktext": [yf(t) for t in y_ticks],
            "domain": list(domains[idx]),
            "anchor": "x",
        }
        if panel.y_log:
            ax["type"] = "log"
        layout[_yaxis_key(idx)] = ax

    return {"data": traces, "layout": layout, "warning": _log_warning_text(report)}
```

注意：`flat` 经 `_ticks` 内部已滤 None；非 log 面板不会产生 None，log 面板已保证有正数，故无需额外兜底。

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_rendering.py -v`
Expected: 全部 PASS（含原有全正 log 测试不回归）。

- [ ] **Step 5: 提交**

```bash
git add app/rendering.py tests/test_rendering.py
git commit -m "feat(rendering): 渲染器接入对数轴 ≤0 过滤并带出警告文案 (issue 18)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 路由层——图表页传警告，迁移路由测试

**Files:**
- Modify: `app/main.py`（`chart_page` 传 `log_warning`；`create_chart` 无需改）
- Test: `tests/test_routes.py`（迁移 `test_upload_log_with_nonpositive_rejected`；新增成功+警告与全 ≤0 仍 400）

**Interfaces:**
- Consumes: `app.rendering.build_plotly_spec` 返回的 `spec["warning"]`。
- Produces: `chart.html` 模板上下文新增 `log_warning: str`（供 Task 4 模板使用）。

- [ ] **Step 1: 迁移并新增路由测试（失败）**

在 `tests/test_routes.py`：把 `test_upload_log_with_nonpositive_rejected`（约 118-127 行）整个函数替换为以下三个测试：

```python
def test_upload_log_partial_nonpositive_now_succeeds(client):
    # X 对数 + 含 0：自动剔除 0 行，应 303 成功(不再 400)
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": False}], {"y": 0})
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "x_log": "on", "layout": layout},
        files={"file": ("data.csv", b"x,y\n0,3.3\n1000,6.6\n10000,9.9\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_chart_page_shows_log_warning(client):
    # Y 对数面板 + 含 0：图表页应出现警告文案
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": True}], {"y": 0})
    loc = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "x_eng": "on", "layout": layout},
        files={"file": ("data.csv", b"x,y\n1000,0\n2000,6.6\n3000,9.9\n", "text/csv")},
        follow_redirects=False,
    ).headers["location"]
    chart_id = loc.rsplit("/", 1)[-1]
    page = client.get(f"/chart/{chart_id}")
    assert "对数 Y 轴包含 ≤0 的值，已自动忽略" in page.text


def test_upload_log_all_nonpositive_still_rejected(client):
    # X 对数但所有 x≤0：无正数可画，仍应 400
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": False}], {"y": 0})
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "x_log": "on", "layout": layout},
        files={"file": ("data.csv", b"x,y\n0,3.3\n-1,6.6\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行新测试，确认失败**

Run: `python -m pytest tests/test_routes.py -v`
Expected: `test_upload_log_partial_nonpositive_now_succeeds` 当前 400（旧逻辑拒绝）→ FAIL；`test_chart_page_shows_log_warning` 找不到文案 → FAIL；`test_upload_log_all_nonpositive_still_rejected` 可能已 PASS。
（注：若 Task 1 已先实现，则 partial 与 all 两条会随之变化；按任务顺序，先跑此步观察。）

- [ ] **Step 3: 改 `app/main.py` 的 `chart_page`**

把 `chart_page` 返回的模板上下文改为携带 `log_warning`：

```python
    parsed = read_csv_bytes(store.read_csv(chart_id))
    spec = build_plotly_spec(parsed, chart.spec)
    return templates.TemplateResponse(
        request,
        "chart.html",
        # 传 dict,由模板 `| tojson` 做 script 上下文安全转义(转义 <>& 防 </script> 破坏块)
        {"chart": chart, "spec": spec, "log_warning": spec["warning"]},
    )
```

（`create_chart` 不改：`validate_spec` 内部已通过 `apply_log_filter` 触发"全 ≤0 → 400"。）

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_routes.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add app/main.py tests/test_routes.py
git commit -m "feat(routes): 对数轴 ≤0 改为剔除出图，图表页传警告 (issue 18)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 图表页警告 toast（前端）

**Files:**
- Modify: `templates/chart.html`（条件渲染 toast 元素 + 约 3 秒后淡出的 JS）
- Modify: `static/app.css`（toast 视觉样式）

**Interfaces:**
- Consumes: 模板上下文 `log_warning: str`（Task 3 提供）。
- Produces: 无下游消费者（终端视图）。

**说明：** 本任务改前端视觉，按 Global Constraints 启用 `frontend-design` skill 指导 toast 排版与样式；不可用时按其原则手工实现，不阻塞。下方为可直接落地的基线，视觉细节可在 skill 指导下微调（建议复用 `app.css` 既有配色变量）。

- [ ] **Step 1: 模板条件渲染 toast + JS**

在 `templates/chart.html` 的 `<div class="wrap">` 内、`<div class="topbar">` 之前插入：

```html
  {% if log_warning %}
  <div id="log-toast" class="toast" role="status">{{ log_warning }}</div>
  {% endif %}
```

在文件底部 `<script src="/static/localtime.js"></script>` 之前插入：

```html
<script>
  // 对数轴 ≤0 警告:显示约 3 秒后淡出移除
  const logToast = document.getElementById("log-toast");
  if (logToast) {
    requestAnimationFrame(() => logToast.classList.add("show"));
    setTimeout(() => {
      logToast.classList.remove("show");
      setTimeout(() => logToast.remove(), 300);
    }, 3000);
  }
</script>
```

- [ ] **Step 2: CSS 样式**

在 `static/app.css` 末尾追加（若项目已有配色 CSS 变量，请改用对应变量）：

```css
.toast {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translate(-50%, -12px);
  max-width: min(92vw, 520px);
  padding: 10px 16px;
  border-radius: 8px;
  background: #2b2f36;
  color: #fff;
  font-size: 14px;
  line-height: 1.4;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.25);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease, transform 0.3s ease;
  z-index: 1000;
}
.toast.show {
  opacity: 1;
  transform: translate(-50%, 0);
}
```

- [ ] **Step 3: 用 HTML 断言核验渲染**

Run: `python -m pytest tests/test_routes.py::test_chart_page_shows_log_warning -v`
Expected: PASS（toast 文案已进入页面 HTML）。

（可选）本地起服务，上传 `x,y` 且 Y 面板设对数、含 0 的 CSV，浏览器看 toast 是否约 3 秒后淡出。

- [ ] **Step 4: 提交**

```bash
git add templates/chart.html static/app.css
git commit -m "feat(ui): 图表页对数轴 ≤0 警告 toast (issue 18)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 全量回归

**Files:** 无新增改动（仅验证）。

- [ ] **Step 1: 跑全量测试**

Run: `python -m pytest -q`
Expected: 全部 PASS（含旧测试不回归）。

- [ ] **Step 2（如有失败）**：用 `superpowers:systematic-debugging` 定位修复，再回到 Step 1。

---

## Self-Review

- **Spec coverage：** 决策 1（图表页 toast）→ Task 3+4；决策 2（逐点剔除/X 删行/非 log 面板保留）→ Task 1；决策 3（全 ≤0 报错）→ Task 1 + Task 3 测试；文案 → Task 2 `_log_warning_text` + Global Constraints；`_ticks` 崩溃 bug → Task 2；`validate_spec` 改造 → Task 1；存储不变 → 无 storage 任务。覆盖完整。
- **旧测试迁移：** `test_spec.py` 的 `test_validate_log_panel_with_nonpositive`、`test_validate_x_log_nonpositive`（Task 1 Step 1 替换）与 `test_routes.py` 的 `test_upload_log_with_nonpositive_rejected`（Task 3 Step 1 替换）均已处理，避免断言旧"拒绝"行为导致回归。
- **依赖方向：** `apply_log_filter` 置于 `app/spec.py`（依赖 parsing），渲染层 import 之，符合 `rendering → spec → parsing`。
- **类型一致：** `apply_log_filter(parsed, spec) -> tuple[ParsedCSV, LogFilterReport]` 跨 spec/rendering 用法一致；`build_plotly_spec` 始终返回含 `"warning"` 键 dict；`LogFilterReport(x_dropped, y_dropped)` 字段名跨任务一致。
- **Placeholder 扫描：** 无 TBD/TODO，所有代码步给出完整代码。
