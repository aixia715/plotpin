# 对数轴自动剔除 ≤0 值并警告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 含 ≤0 值的 CSV 在对数坐标下不再被拒绝，而是自动剔除对数轴上的 ≤0 点照常出图，并在图表页弹约 3 秒警告 toast。

**Architecture:** 纯逻辑层新增 `apply_log_filter` 完成剔除与"全 ≤0 报错"，并报告命中了哪条轴；渲染层两个渲染器内部统一调用它，保证三个入口（上传校验、交互页、PNG/SVG）一致；Plotly spec 顺带带出警告文案，图表页据此渲染 toast。警告实时计算、不持久化，存储 schema 不变。

**Tech Stack:** FastAPI + Jinja2 + 原生 JS + Plotly.js；matplotlib（静态出图）；pytest（TDD）。

## Global Constraints

- 依赖方向只能从外往里指：路由 → 数据/逻辑；逻辑层内部 `rendering → parsing → eng_notation`。不得反向依赖。
- 新业务逻辑优先放纯逻辑层并配单测，保持 `app/main.py` 薄。
- 改动遵循 TDD：先写失败测试再实现。纯逻辑层是测试投入重点。
- 测试在 `tests/`，用 `pytest` 运行。
- 后端时间一律 UTC；本任务不涉及时间展示。
- 改前端（`templates/`、`static/`）做视觉时启用 `frontend-design` skill（不可用则按其原则手工实现，不阻塞）。
- 警告文案逐字固定：
  - 仅 X：`对数 X 轴包含 ≤0 的值，已自动忽略`
  - 仅 Y：`对数 Y 轴包含 ≤0 的值，已自动忽略`
  - X 和 Y：`对数 X 轴和 Y 轴包含 ≤0 的值，已自动忽略`
  - 无剔除：空串 `""`
- 全 ≤0 报错文案：`X 轴所有值 ≤0，无法使用对数坐标` / `Y 轴所有值 ≤0，无法使用对数坐标`（须含子串「对数」？否——现有路由测试只断言 `"对数"`，本计划 Task 3 会改这条断言，见该任务）。

---

### Task 1: 纯逻辑层 `apply_log_filter` 与 `LogFilterReport`

**Files:**
- Modify: `app/parsing.py`（放宽 `ParsedCSV.ys` 类型；删除 `check_log_positivity`；新增 `LogFilterReport` 与 `apply_log_filter`）
- Test: `tests/test_parsing.py`（替换 4 个旧 `check_log_positivity` 测试为新函数测试）

**Interfaces:**
- Consumes: 现有 `ParsedCSV`（字段 `x_label: str`、`x: list[float]`、`y_labels: list[str]`、`ys`）、`CSVParseError`。
- Produces:
  - `class LogFilterReport` —— `@dataclass`，字段 `x_dropped: bool = False`、`y_dropped: bool = False`。
  - `apply_log_filter(parsed: ParsedCSV, x_log: bool, y_log: bool) -> tuple[ParsedCSV, LogFilterReport]`
    - `x_log` 真：删除所有 `x <= 0` 的行（x 与各 y 按下标对齐删除）；有删除则 `x_dropped=True`；删空则抛 `CSVParseError("X 轴所有值 ≤0，无法使用对数坐标")`。
    - `y_log` 真：把每条曲线 `y <= 0` 的点置 `None`；有置空则 `y_dropped=True`；若全部曲线无任何正数则抛 `CSVParseError("Y 轴所有值 ≤0，无法使用对数坐标")`。
    - 过滤后 `ParsedCSV.ys` 元素类型为 `float | None`。
  - `ParsedCSV.ys` 类型注解放宽为 `list[list[float | None]]`。

- [ ] **Step 1: 替换旧 log 测试为新失败测试**

把 `tests/test_parsing.py` 中这 4 个旧测试整体删除：`test_log_ok_when_all_positive`、`test_log_rejects_nonpositive_y`、`test_log_rejects_nonpositive_x`、`test_no_check_when_log_off`（它们引用即将删除的 `check_log_positivity`）。保留文件顶部 `_parsed()` 辅助函数之外的其余内容。然后在文件末尾追加：

```python
def test_apply_log_filter_off_returns_unchanged():
    from app.parsing import apply_log_filter
    p = ParsedCSV("x", [0.0, 10.0], ["y"], [[-1.0, 20.0]])
    out, report = apply_log_filter(p, False, False)
    assert out.x == [0.0, 10.0]
    assert out.ys == [[-1.0, 20.0]]
    assert report.x_dropped is False and report.y_dropped is False


def test_apply_log_filter_x_drops_nonpositive_rows():
    from app.parsing import apply_log_filter
    p = ParsedCSV("x", [0.0, 10.0, 100.0], ["y"], [[1.0, 2.0, 3.0]])
    out, report = apply_log_filter(p, True, False)
    assert out.x == [10.0, 100.0]
    assert out.ys == [[2.0, 3.0]]          # y 同步对齐删除
    assert report.x_dropped is True
    assert report.y_dropped is False


def test_apply_log_filter_y_gaps_nonpositive_points():
    from app.parsing import apply_log_filter
    p = ParsedCSV("x", [1.0, 10.0, 100.0], ["a", "b"], [[0.0, 5.0, 50.0], [1.0, 2.0, 3.0]])
    out, report = apply_log_filter(p, False, True)
    assert out.ys[0] == [None, 5.0, 50.0]  # ≤0 点置空成缺口
    assert out.ys[1] == [1.0, 2.0, 3.0]    # 其他曲线不受影响
    assert report.y_dropped is True
    assert report.x_dropped is False


def test_apply_log_filter_both_axes():
    from app.parsing import apply_log_filter
    p = ParsedCSV("x", [0.0, 10.0, 100.0], ["y"], [[5.0, -1.0, 50.0]])
    out, report = apply_log_filter(p, True, True)
    assert out.x == [10.0, 100.0]          # x≤0 行先删
    assert out.ys == [[None, 50.0]]        # 剩余里 y≤0 置空
    assert report.x_dropped is True and report.y_dropped is True


def test_apply_log_filter_all_positive_no_drop():
    from app.parsing import apply_log_filter
    p = ParsedCSV("x", [1.0, 10.0], ["y"], [[2.0, 20.0]])
    out, report = apply_log_filter(p, True, True)
    assert out.x == [1.0, 10.0]
    assert out.ys == [[2.0, 20.0]]
    assert report.x_dropped is False and report.y_dropped is False


def test_apply_log_filter_x_all_nonpositive_raises():
    from app.parsing import apply_log_filter
    p = ParsedCSV("x", [0.0, -1.0], ["y"], [[2.0, 20.0]])
    with pytest.raises(CSVParseError):
        apply_log_filter(p, True, False)


def test_apply_log_filter_y_all_nonpositive_raises():
    from app.parsing import apply_log_filter
    p = ParsedCSV("x", [1.0, 10.0], ["a", "b"], [[0.0, -1.0], [-2.0, 0.0]])
    with pytest.raises(CSVParseError):
        apply_log_filter(p, False, True)


def test_apply_log_filter_y_one_series_all_nonpositive_ok():
    from app.parsing import apply_log_filter
    p = ParsedCSV("x", [1.0, 10.0], ["a", "b"], [[0.0, -1.0], [2.0, 20.0]])
    out, report = apply_log_filter(p, False, True)
    assert out.ys[0] == [None, None]       # 整条置空但不报错
    assert out.ys[1] == [2.0, 20.0]
    assert report.y_dropped is True
```

- [ ] **Step 2: 运行新测试，确认失败**

Run: `python -m pytest tests/test_parsing.py -v`
Expected: 新增 8 个测试 FAIL（`ImportError: cannot import name 'apply_log_filter'`）。

- [ ] **Step 3: 实现 `apply_log_filter`，删除 `check_log_positivity`**

在 `app/parsing.py`：把 `ParsedCSV` 的 `ys` 注解改为 `ys: list[list[float | None]]`。删除现有 `check_log_positivity` 函数。在文件末尾追加：

```python
@dataclass
class LogFilterReport:
    x_dropped: bool = False
    y_dropped: bool = False


def apply_log_filter(
    parsed: ParsedCSV, x_log: bool, y_log: bool
) -> tuple[ParsedCSV, LogFilterReport]:
    x = list(parsed.x)
    ys = [list(col) for col in parsed.ys]
    x_dropped = False
    y_dropped = False

    if x_log:
        keep = [i for i, v in enumerate(x) if v is not None and v > 0]
        if len(keep) != len(x):
            x_dropped = True
        if not keep:
            raise CSVParseError("X 轴所有值 ≤0，无法使用对数坐标")
        x = [x[i] for i in keep]
        ys = [[col[i] for i in keep] for col in ys]

    if y_log:
        any_positive = False
        for col in ys:
            for j, v in enumerate(col):
                if v is None:
                    continue
                if v <= 0:
                    col[j] = None
                    y_dropped = True
                else:
                    any_positive = True
        if not any_positive:
            raise CSVParseError("Y 轴所有值 ≤0，无法使用对数坐标")

    filtered = ParsedCSV(
        x_label=parsed.x_label,
        x=x,
        y_labels=list(parsed.y_labels),
        ys=ys,
    )
    return filtered, LogFilterReport(x_dropped, y_dropped)
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_parsing.py -v`
Expected: 全部 PASS（含新增 8 个）。

- [ ] **Step 5: 提交**

```bash
git add app/parsing.py tests/test_parsing.py
git commit -m "feat(parsing): apply_log_filter 剔除对数轴 ≤0 值并报告 (issue 18)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 渲染层接入过滤 + Plotly spec 带警告文案

**Files:**
- Modify: `app/rendering.py`（`_ticks` 忽略 None；`build_plotly_spec` 调过滤、null 缺口、customdata 保护、返回 `warning`；`render_static` 调过滤、None→NaN；新增 `_log_warning_text`）
- Test: `tests/test_rendering.py`（追加测试）

**Interfaces:**
- Consumes: `app.parsing.apply_log_filter`、`LogFilterReport`、`ParsedCSV`；现有 `log_ticks` / `nice_ticks` / `format_eng` / `format_plain`。
- Produces:
  - `_log_warning_text(report: LogFilterReport) -> str` —— 按 Global Constraints 的文案表返回，无剔除返回 `""`。
  - `build_plotly_spec(...)` 返回 dict 新增键 `"warning": str`（`{"data": ..., "layout": ..., "warning": ...}`）。
  - `build_plotly_spec` / `render_static` 内部对传入 `parsed` 先做 `apply_log_filter`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_rendering.py` 顶部确认已 `from app.parsing import ParsedCSV`（若无则加）。追加：

```python
def test_ticks_ignore_none():
    from app.rendering import _ticks
    # 含 None 不应让 min/max 崩溃；这里只验证能算出刻度
    ticks = _ticks([None, 1.0, 10.0, 100.0], True)
    assert ticks  # 非空
    assert all(t > 0 for t in ticks)


def test_build_spec_y_log_nulls_nonpositive_and_warns():
    from app.rendering import build_plotly_spec
    p = ParsedCSV("x", [1.0, 10.0, 100.0], ["y"], [[0.0, 5.0, 50.0]])
    spec = build_plotly_spec(p, "T", "X", "Y", False, False, False, True)
    assert spec["data"][0]["y"][0] is None          # ≤0 点变 null 缺口
    assert spec["data"][0]["y"][1:] == [5.0, 50.0]
    assert spec["warning"] == "对数 Y 轴包含 ≤0 的值，已自动忽略"
    # customdata 对 None 点不应崩，且该点 y 文案为 None
    assert spec["data"][0]["customdata"][0][1] is None


def test_build_spec_x_log_drops_rows_and_warns():
    from app.rendering import build_plotly_spec
    p = ParsedCSV("x", [0.0, 10.0, 100.0], ["y"], [[1.0, 2.0, 3.0]])
    spec = build_plotly_spec(p, "T", "X", "Y", False, False, True, False)
    assert spec["data"][0]["x"] == [10.0, 100.0]
    assert spec["data"][0]["y"] == [2.0, 3.0]
    assert spec["warning"] == "对数 X 轴包含 ≤0 的值，已自动忽略"


def test_build_spec_both_axes_warning_text():
    from app.rendering import build_plotly_spec
    p = ParsedCSV("x", [0.0, 10.0], ["y"], [[-1.0, 20.0]])
    spec = build_plotly_spec(p, "T", "X", "Y", False, False, True, True)
    assert spec["warning"] == "对数 X 轴和 Y 轴包含 ≤0 的值，已自动忽略"


def test_build_spec_no_warning_when_clean():
    from app.rendering import build_plotly_spec
    p = ParsedCSV("x", [1.0, 10.0], ["y"], [[2.0, 20.0]])
    spec = build_plotly_spec(p, "T", "X", "Y", False, False, True, True)
    assert spec["warning"] == ""


def test_render_static_with_gaps_does_not_crash():
    from app.rendering import render_static
    p = ParsedCSV("x", [1.0, 10.0, 100.0], ["y"], [[0.0, 5.0, 50.0]])
    data = render_static(p, "T", "X", "Y", False, False, False, True, "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: 运行新测试，确认失败**

Run: `python -m pytest tests/test_rendering.py -v`
Expected: 新增测试 FAIL（`spec["warning"]` KeyError；或 `_ticks` 对 None 报 `TypeError`）。

- [ ] **Step 3: 实现渲染层改动**

在 `app/rendering.py`：

把 `from app.parsing import ParsedCSV` 那行改为：

```python
from app.parsing import LogFilterReport, ParsedCSV, apply_log_filter  # noqa: E402
```

把 `_ticks` 改为忽略 None：

```python
def _ticks(values, use_log: bool):
    vals = [v for v in values if v is not None]
    lo, hi = min(vals), max(vals)
    return log_ticks(lo, hi) if use_log else nice_ticks(lo, hi)
```

在 `_ticks` 之后新增文案函数：

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

把 `render_static` 函数体开头（`fig, ax = plt.subplots(...)` 之前）插入过滤，并在画图时把 None 转 NaN：

```python
def render_static(parsed, title, x_title, y_title, x_eng, y_eng, x_log, y_log, fmt):
    parsed, _report = apply_log_filter(parsed, x_log, y_log)
    fig, ax = plt.subplots(figsize=(8, 5))
    try:
        for label, ys in zip(parsed.y_labels, parsed.ys):
            ys_plot = [float("nan") if v is None else v for v in ys]
            ax.plot(parsed.x, ys_plot, label=label)
```

（其余 `render_static` 内容保持不变。）

把 `build_plotly_spec` 改为开头过滤、customdata 保护、末尾带 warning：

```python
def build_plotly_spec(parsed, title, x_title, y_title, x_eng, y_eng, x_log, y_log):
    parsed, report = apply_log_filter(parsed, x_log, y_log)
    xf = _formatter(x_eng)
    yf = _formatter(y_eng)

    traces = []
    for label, ys in zip(parsed.y_labels, parsed.ys):
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": label,
            "x": parsed.x,
            "y": ys,
            "customdata": [
                [xf(xv), (yf(yv) if yv is not None else None)]
                for xv, yv in zip(parsed.x, ys)
            ],
            "hovertemplate": (
                f"{x_title}: %{{customdata[0]}}<br>"
                f"{y_title}: %{{customdata[1]}}<extra>%{{fullData.name}}</extra>"
            ),
        })

    x_ticks = _ticks(parsed.x, x_log)
    all_y = [v for ys in parsed.ys for v in ys]
    y_ticks = _ticks(all_y, y_log)

    xaxis = {
        "title": {"text": x_title},
        "tickvals": x_ticks,
        "ticktext": [xf(t) for t in x_ticks],
    }
    yaxis = {
        "title": {"text": y_title},
        "tickvals": y_ticks,
        "ticktext": [yf(t) for t in y_ticks],
    }
    if x_log:
        xaxis["type"] = "log"
    if y_log:
        yaxis["type"] = "log"

    layout = {"title": {"text": title}, "xaxis": xaxis, "yaxis": yaxis}
    return {"data": traces, "layout": layout, "warning": _log_warning_text(report)}
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python -m pytest tests/test_rendering.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add app/rendering.py tests/test_rendering.py
git commit -m "feat(rendering): 渲染器接入对数轴 ≤0 过滤并带出警告文案 (issue 18)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 路由层——上传校验改为过滤、图表页传警告

**Files:**
- Modify: `app/main.py`（import 改用 `apply_log_filter`；`create_chart` 用过滤做校验；`chart_page` 传 `log_warning`）
- Test: `tests/test_routes.py`（改写 `test_upload_log_with_nonpositive_rejected`；新增成功+警告与全 ≤0 仍 400 的测试）

**Interfaces:**
- Consumes: `app.parsing.apply_log_filter`、`CSVParseError`；`app.rendering.build_plotly_spec` 返回的 `spec["warning"]`。
- Produces: `chart.html` 模板上下文新增 `log_warning: str`（供 Task 4 的模板使用）。

- [ ] **Step 1: 改写并新增路由测试（失败）**

在 `tests/test_routes.py`：把现有 `test_upload_log_with_nonpositive_rejected` 整个函数替换为以下三个测试（语义从「拒绝」改为「剔除并 303 + 警告」，并保留"全 ≤0 仍 400"）：

```python
def test_upload_log_with_nonpositive_now_succeeds(client):
    # X 对数 + 含 0：自动剔除 0 行，应 303 成功(不再 400)
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "y_title": "Y", "x_log": "on"},
        files={"file": ("data.csv", b"x,y\n0,3.3\n1000,6.6\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_chart_page_shows_log_warning(client):
    # Y 对数 + 含 0：图表页应出现警告文案
    loc = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "y_title": "Y", "y_log": "on"},
        files={"file": ("data.csv", b"x,y\n1000,0\n2000,6.6\n", "text/csv")},
        follow_redirects=False,
    ).headers["location"]
    chart_id = loc.rsplit("/", 1)[-1]
    page = client.get(f"/chart/{chart_id}")
    assert "对数 Y 轴包含 ≤0 的值，已自动忽略" in page.text


def test_upload_log_all_nonpositive_still_rejected(client):
    # X 对数但所有 x≤0：无正数可画，仍应 400
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "y_title": "Y", "x_log": "on"},
        files={"file": ("data.csv", b"x,y\n0,3.3\n-1,6.6\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: 运行新测试，确认失败**

Run: `python -m pytest tests/test_routes.py -v`
Expected: `test_upload_log_with_nonpositive_now_succeeds` 当前得 400（旧逻辑拒绝）→ FAIL；`test_chart_page_shows_log_warning` 找不到文案 → FAIL；`test_upload_log_all_nonpositive_still_rejected` 可能已 PASS（旧逻辑也 400）。

- [ ] **Step 3: 改 `app/main.py`**

把第 10 行 import 改为：

```python
from app.parsing import CSVParseError, apply_log_filter, read_csv_bytes
```

`create_chart` 里把校验行替换：

```python
        parsed = read_csv_bytes(raw)             # 解析 + 逐格校验
        apply_log_filter(parsed, x_log, y_log)   # 对数轴 ≤0 剔除校验(全 ≤0 才报错)
```

`chart_page` 里把 spec 取出后传给模板：

```python
    spec = build_plotly_spec(
        parsed, chart.title, chart.x_title, chart.y_title,
        chart.x_eng, chart.y_eng, chart.x_log, chart.y_log,
    )
    return templates.TemplateResponse(
        request,
        "chart.html",
        {
            "chart": chart,
            "spec_json": json.dumps(spec),
            "log_warning": spec["warning"],
        },
    )
```

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

**说明：** 本任务改前端视觉，按 Global Constraints 启用 `frontend-design` skill 指导 toast 的排版与样式；不可用时按其原则手工实现，不阻塞。下方代码为可直接落地的基线，视觉细节可在 skill 指导下微调。

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
  const toast = document.getElementById("log-toast");
  if (toast) {
    requestAnimationFrame(() => toast.classList.add("show"));
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }
</script>
```

- [ ] **Step 2: CSS 样式**

在 `static/app.css` 末尾追加（颜色/圆角等贴合现有设计变量；若项目用了 CSS 变量请改用对应变量）：

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

- [ ] **Step 3: 手动核验渲染（无浏览器时用 HTML 断言兜底）**

Run: `python -m pytest tests/test_routes.py::test_chart_page_shows_log_warning -v`
Expected: PASS（确认 toast 文案已进入页面 HTML）。

（可选）本地起服务用浏览器上传 `x,y\n1000,0\n2000,6.6\n`（Y 对数）查看 toast 是否出现约 3 秒后淡出。

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

- **Spec coverage：** 决策 1（图表页 toast）→ Task 3+4；决策 2（逐点剔除/X 删行）→ Task 1；决策 3（全 ≤0 报错）→ Task 1 + Task 3 测试；文案 → Task 2 `_log_warning_text` + Global Constraints；`_ticks` 崩溃 bug → Task 2；存储不变 → 无 storage 任务（符合 spec）。覆盖完整。
- **旧测试迁移：** `check_log_positivity` 的 4 个 parsing 测试（Task 1 Step 1 删除）与路由 `test_upload_log_with_nonpositive_rejected`（Task 3 Step 1 改写）均已处理，避免引用已删函数导致回归。
- **类型一致：** `apply_log_filter` 返回 `tuple[ParsedCSV, LogFilterReport]`，渲染层与路由层用法一致；`build_plotly_spec` 始终返回含 `"warning"` 键的 dict；`LogFilterReport(x_dropped, y_dropped)` 字段名跨任务一致。
- **Placeholder 扫描：** 无 TBD/TODO，所有代码步给出完整代码。
