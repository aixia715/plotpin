# 多面板曲线分配 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让一个分享页包含多个纵向堆叠、共享 X 轴的独立面板，用户在创建时把每条曲线（Y 列）指派到某个面板或隐藏。

**Architecture:** 引入纯逻辑数据结构 `ChartSpec`（含页面级 X 配置 + 每面板独立 Y 配置 + 曲线→面板分配）。`rendering.py` 两个出图函数改吃 `ChartSpec`；`storage.py` 用干净 schema 把 `ChartSpec` 序列化为 `spec_json`；`main.py` 路由组装/读取 `ChartSpec`；前端用 JS 读 CSV 表头生成分配 UI 并拼出 `layout` JSON。

**Tech Stack:** FastAPI、Jinja2、Plotly.js、matplotlib、pandas、SQLite、pytest。

## Global Constraints

- 三层架构，依赖只能从外往里指：路由 → 数据/逻辑，逻辑层内部 `rendering → spec → parsing → eng_notation`。不得反向依赖。
- 纯逻辑层（`spec` / `rendering` / `parsing` / `eng_notation` / `ids`）零 Web/DB 依赖，是测试投入重点。
- TDD：每个改动先写失败测试再实现。
- 项目未上线，**无需兼容老数据**；可用干净 schema。
- 永久链接语义不变：分享 id 对应的页面 / PNG / SVG 链接与缓存策略不变。
- 展示给用户的时间一律前端转本地时间（本特性不新增时间展示，沿用现有 `created_at` + `localtime.js`）。
- 校验失败统一抛 `app.parsing.CSVParseError`，由路由转 400 并在 `index.html` 回显。
- 中文回答；提交信息中文，结尾带 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

## 重构期绿灯说明

本计划是一次贯通调用链的重构。Task 1–2 新增 `spec.py`，仓库保持全绿。Task 3–5 分别改 `rendering.py`、`storage.py`，期间这些模块**自己的测试文件全绿**，但 `app/main.py` 因调用旧签名而无法导入，故 `test_routes.py` 会暂时失败——这是预期的。**完整 `pytest` 全绿在 Task 6（路由）结束时恢复。** 每个任务仍各自提交。

## File Structure

- `app/spec.py`（新建）— `PanelSpec` / `ChartSpec` 数据结构、序列化、`validate_spec` 校验。纯逻辑，仅依赖 `parsing`。
- `app/rendering.py`（改）— `build_plotly_spec(parsed, spec)`、`render_static(parsed, spec, fmt)` 改吃 `ChartSpec`，生成多面板。
- `app/storage.py`（改）— 干净 schema `charts(id, title, created_at, spec_json)`；`Chart` 持有 `ChartSpec`。
- `app/main.py`（改）— `POST /charts` 收 `layout` JSON 组装 `ChartSpec`；`GET` 三出口统一用 `chart.spec`。
- `templates/index.html`（改）+ `static/builder.js`（新建）— 读 CSV 表头生成「面板数 + 每曲线下拉 + 每面板 Y 配置」，提交前拼 `layout` JSON。
- `templates/chart.html`（改）— 绘图容器高度按面板数自适应。
- 测试：`tests/test_spec.py`（新）、`tests/test_rendering.py`（改）、`tests/test_storage.py`（改）、`tests/test_routes.py`（改）。

---

### Task 1: `ChartSpec` 数据结构与序列化

**Files:**
- Create: `app/spec.py`
- Test: `tests/test_spec.py`

**Interfaces:**
- Consumes: `app.parsing.ParsedCSV`、`app.parsing.CSVParseError`
- Produces:
  - `PanelSpec(y_title: str, y_eng: bool, y_log: bool)`（dataclass）
  - `ChartSpec(title: str, x_title: str, x_eng: bool, x_log: bool, panels: list[PanelSpec], assign: dict[str, int | None])`（dataclass）
  - `ChartSpec.to_json(self) -> str`
  - `ChartSpec.from_json(cls, s: str) -> ChartSpec`（classmethod）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_spec.py
from app.spec import ChartSpec, PanelSpec


def _spec() -> ChartSpec:
    return ChartSpec(
        title="T", x_title="X", x_eng=True, x_log=False,
        panels=[PanelSpec("增益", True, False), PanelSpec("相位", False, True)],
        assign={"gain": 0, "phase": 1, "noise": None},
    )


def test_to_from_json_roundtrip():
    spec = _spec()
    restored = ChartSpec.from_json(spec.to_json())
    assert restored == spec


def test_from_json_normalizes_types():
    # 字符串/数字布尔与整型下标都应被归一
    raw = (
        '{"title":"T","x_title":"X","x_eng":1,"x_log":0,'
        '"panels":[{"y_title":"Y","y_eng":0,"y_log":1}],'
        '"assign":{"a":"0","b":null}}'
    )
    spec = ChartSpec.from_json(raw)
    assert spec.x_eng is True and spec.x_log is False
    assert spec.panels[0].y_eng is False and spec.panels[0].y_log is True
    assert spec.assign == {"a": 0, "b": None}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_spec.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.spec'`）

- [ ] **Step 3: 写最小实现**

```python
# app/spec.py
import json
from dataclasses import asdict, dataclass

from app.parsing import CSVParseError, ParsedCSV  # noqa: F401  (CSVParseError/ParsedCSV 供 validate_spec 使用)


@dataclass
class PanelSpec:
    y_title: str
    y_eng: bool
    y_log: bool


@dataclass
class ChartSpec:
    title: str
    x_title: str
    x_eng: bool
    x_log: bool
    panels: list[PanelSpec]
    assign: dict[str, int | None]

    def to_json(self) -> str:
        return json.dumps(
            {
                "title": self.title,
                "x_title": self.x_title,
                "x_eng": self.x_eng,
                "x_log": self.x_log,
                "panels": [asdict(p) for p in self.panels],
                "assign": self.assign,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, s: str) -> "ChartSpec":
        d = json.loads(s)
        return cls(
            title=d["title"],
            x_title=d["x_title"],
            x_eng=bool(d["x_eng"]),
            x_log=bool(d["x_log"]),
            panels=[
                PanelSpec(p["y_title"], bool(p["y_eng"]), bool(p["y_log"]))
                for p in d["panels"]
            ],
            assign={k: (None if v is None else int(v)) for k, v in d["assign"].items()},
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_spec.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/spec.py tests/test_spec.py
git commit -m "添加 ChartSpec/PanelSpec 数据结构与序列化（issue 11）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `validate_spec` 校验

**Files:**
- Modify: `app/spec.py`
- Test: `tests/test_spec.py`

**Interfaces:**
- Consumes: `ChartSpec`、`PanelSpec`、`app.parsing.ParsedCSV`、`app.parsing.CSVParseError`
- Produces: `validate_spec(spec: ChartSpec, parsed: ParsedCSV) -> None`（校验失败抛 `CSVParseError`）

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_spec.py
import pytest

from app.parsing import CSVParseError, ParsedCSV
from app.spec import validate_spec


def _parsed() -> ParsedCSV:
    return ParsedCSV(
        x_label="freq", x=[1.0, 2.0, 3.0],
        y_labels=["gain", "phase", "noise"],
        ys=[[1.0, 2.0, 3.0], [-1.0, 0.5, 2.0], [10.0, 20.0, 30.0]],
    )


def test_validate_ok():
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("a", True, False), PanelSpec("b", True, False)],
                     {"gain": 0, "phase": 1, "noise": None})
    validate_spec(spec, _parsed())  # 不抛异常


def test_validate_empty_panels():
    spec = ChartSpec("T", "X", True, False, [],
                     {"gain": None, "phase": None, "noise": None})
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_assign_keys_mismatch():
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, False)],
                     {"gain": 0})  # 少了 phase/noise
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_panel_index_out_of_range():
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, False)],
                     {"gain": 0, "phase": 5, "noise": None})
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_all_hidden():
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, False)],
                     {"gain": None, "phase": None, "noise": None})
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_log_panel_with_nonpositive():
    # phase 含 -1，归到对数面板 0 → 报错
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)],
                     {"gain": 0, "phase": 0, "noise": None})
    with pytest.raises(CSVParseError):
        validate_spec(spec, _parsed())


def test_validate_log_panel_positive_ok():
    # 对数面板只含全正的 gain/noise，phase 隐藏 → 通过
    spec = ChartSpec("T", "X", True, False, [PanelSpec("a", True, True)],
                     {"gain": 0, "phase": None, "noise": 0})
    validate_spec(spec, _parsed())


def test_validate_x_log_nonpositive():
    parsed = ParsedCSV("f", [0.0, 1.0, 2.0], ["gain"], [[1.0, 2.0, 3.0]])
    spec = ChartSpec("T", "X", True, True, [PanelSpec("a", True, False)], {"gain": 0})
    with pytest.raises(CSVParseError):
        validate_spec(spec, parsed)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_spec.py -v`
Expected: FAIL（`ImportError: cannot import name 'validate_spec'`）

- [ ] **Step 3: 写最小实现**

```python
# 追加到 app/spec.py
def validate_spec(spec: ChartSpec, parsed: ParsedCSV) -> None:
    if not spec.panels:
        raise CSVParseError("至少需要一个面板")
    if set(spec.assign.keys()) != set(parsed.y_labels):
        raise CSVParseError("曲线分配与数据列不一致")
    n = len(spec.panels)
    for col, idx in spec.assign.items():
        if idx is not None and not (0 <= idx < n):
            raise CSVParseError(f"曲线 `{col}` 指派到不存在的面板")
    if all(idx is None for idx in spec.assign.values()):
        raise CSVParseError("至少需要显示一条曲线")
    if spec.x_log and any(v <= 0 for v in parsed.x):
        raise CSVParseError("X 轴含 ≤0 值,无法使用对数坐标")
    col_values = dict(zip(parsed.y_labels, parsed.ys))
    for pi, panel in enumerate(spec.panels):
        if not panel.y_log:
            continue
        for col, idx in spec.assign.items():
            if idx == pi and any(v <= 0 for v in col_values[col]):
                raise CSVParseError(f"面板 {pi + 1} 含 ≤0 值,无法使用对数坐标")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_spec.py -v`
Expected: PASS（全部 spec 测试）

- [ ] **Step 5: 提交**

```bash
git add app/spec.py tests/test_spec.py
git commit -m "添加 validate_spec 多面板分配校验（issue 11）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `build_plotly_spec` 改吃 `ChartSpec`（多面板）

**Files:**
- Modify: `app/rendering.py:61-100`（`build_plotly_spec`）
- Test: `tests/test_rendering.py`

> 注：本任务后 `app/main.py` 仍调用旧签名，`test_routes.py` 会暂时失败，属预期（见「重构期绿灯说明」）。本任务只运行 `tests/test_rendering.py`。

**Interfaces:**
- Consumes: `app.spec.ChartSpec`、`app.spec.PanelSpec`、`app.parsing.ParsedCSV`
- Produces: `build_plotly_spec(parsed: ParsedCSV, spec: ChartSpec) -> dict`
  - 返回 `{"data": [...traces], "layout": {...}}`
  - 面板 i（0=顶部）对应 layout 键 `"yaxis"`（i==0）/`"yaxis{i+1}"`（i>0）；该面板曲线 trace 的 `"yaxis"` 为 `"y"`（i==0）/`"y{i+1}"`
  - 隐藏曲线（`assign[col] is None`）不进 traces
  - 每面板 yaxis：`title.text`=该面板 `y_title`；`tickvals`/`ticktext` 按该面板 `y_eng`；`type="log"` 当该面板 `y_log`
  - 共享 X 轴在 `layout["xaxis"]`，`type="log"` 当 `spec.x_log`

- [ ] **Step 1: 改写测试**

把 `tests/test_rendering.py` 顶部改为同时构造 `ChartSpec`，替换两个 plotly 测试，并新增多面板测试：

```python
import math

from app.parsing import ParsedCSV
from app.rendering import build_plotly_spec, render_static
from app.spec import ChartSpec, PanelSpec


def _sample() -> ParsedCSV:
    return ParsedCSV(
        x_label="freq",
        x=[1000.0, 2000.0, 3000.0],
        y_labels=["gain", "phase"],
        ys=[[3.3, 6.6, 9.9], [0.1, 0.2, 0.3]],
    )


def _one_panel(x_eng=True, y_eng=False, x_log=False, y_log=False) -> ChartSpec:
    # 单面板：gain、phase 都在面板 0
    return ChartSpec("T", "X", x_eng, x_log,
                     [PanelSpec("Y", y_eng, y_log)],
                     {"gain": 0, "phase": 0})


def test_build_plotly_spec_structure():
    spec = build_plotly_spec(_sample(), _one_panel(x_eng=True, y_eng=False))
    assert len(spec["data"]) == 2
    assert spec["data"][0]["name"] == "gain"
    assert spec["data"][0]["x"] == [1000.0, 2000.0, 3000.0]
    assert spec["layout"]["title"]["text"] == "T"
    assert spec["layout"]["xaxis"].get("type") != "log"
    assert any("k" in t for t in spec["layout"]["xaxis"]["ticktext"])
    assert all(not any(ch.isalpha() for ch in t)
               for t in spec["layout"]["yaxis"]["ticktext"])


def test_build_plotly_spec_log_axis():
    spec = build_plotly_spec(_sample(), _one_panel(x_eng=True, y_eng=True, x_log=True, y_log=False))
    assert spec["layout"]["xaxis"]["type"] == "log"
    assert spec["layout"]["yaxis"].get("type") != "log"
    assert all(abs(round(math.log10(t)) - math.log10(t)) < 1e-9
               for t in spec["layout"]["xaxis"]["tickvals"])


def test_build_plotly_spec_two_panels():
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("上", True, False), PanelSpec("下", True, True)],
                     {"gain": 0, "phase": 1})
    out = build_plotly_spec(_sample(), spec)
    by_name = {t["name"]: t for t in out["data"]}
    assert by_name["gain"]["yaxis"] == "y"
    assert by_name["phase"]["yaxis"] == "y2"
    assert out["layout"]["yaxis"]["title"]["text"] == "上"
    assert out["layout"]["yaxis2"]["title"]["text"] == "下"
    # 面板 1 为对数
    assert out["layout"]["yaxis"].get("type") != "log"
    assert out["layout"]["yaxis2"]["type"] == "log"


def test_build_plotly_spec_hidden_curve_excluded():
    spec = ChartSpec("T", "X", True, False, [PanelSpec("Y", True, False)],
                     {"gain": 0, "phase": None})
    out = build_plotly_spec(_sample(), spec)
    assert [t["name"] for t in out["data"]] == ["gain"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_rendering.py -v`
Expected: FAIL（`build_plotly_spec` 旧签名 / 缺多面板逻辑）

- [ ] **Step 3: 写实现**

替换 `app/rendering.py` 中 `build_plotly_spec`：

```python
def _yaxis_key(idx: int) -> str:
    return "yaxis" if idx == 0 else f"yaxis{idx + 1}"


def _yref(idx: int) -> str:
    return "y" if idx == 0 else f"y{idx + 1}"


def _panel_domains(n: int, gap: float = 0.08) -> list[tuple[float, float]]:
    # 面板 0 在顶部；返回每个面板的 [bottom, top]
    h = (1 - gap * (n - 1)) / n
    domains = []
    for i in range(n):
        top = 1 - i * (h + gap)
        domains.append((top - h, top))
    return domains


def build_plotly_spec(parsed, spec):
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
            "customdata": [[xf(xv), yf(yv)] for xv, yv in zip(parsed.x, ys)],
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
        members = [col_values[c] for c, i in spec.assign.items() if i == idx]
        flat = [v for ys in members for v in ys] or [0.0, 1.0]
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

    return {"data": traces, "layout": layout}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_rendering.py -v`
Expected: PASS（plotly 相关测试；`render_static` 测试此时仍是旧签名，将在 Task 4 改）

> 若 `render_static` 旧测试此刻报错，本步只关注 `build_plotly_spec` 的四个测试通过；`render_static` 测试在 Task 4 修复。可用 `-k build_plotly_spec` 只跑本任务测试：
> Run: `pytest tests/test_rendering.py -k build_plotly_spec -v`

- [ ] **Step 5: 提交**

```bash
git add app/rendering.py tests/test_rendering.py
git commit -m "build_plotly_spec 改吃 ChartSpec 生成多面板（issue 11）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `render_static` 改吃 `ChartSpec`（多面板静态出图）

**Files:**
- Modify: `app/rendering.py:37-58`（`render_static`）
- Test: `tests/test_rendering.py`

> 本任务后 `tests/test_rendering.py` 应整体全绿；`test_routes.py` 仍暂红（Task 6 恢复）。

**Interfaces:**
- Consumes: `app.spec.ChartSpec`、`app.parsing.ParsedCSV`
- Produces: `render_static(parsed: ParsedCSV, spec: ChartSpec, fmt: str) -> bytes`
  - `fmt` 为 `"png"` 或 `"svg"`；纵向堆叠 `len(spec.panels)` 个子图，共享 X 轴；输出单张图字节

- [ ] **Step 1: 改写测试**

替换 `tests/test_rendering.py` 中三个 `render_static` 测试：

```python
def test_render_png_returns_png_bytes():
    data = render_static(_sample(), _one_panel(x_eng=True, y_eng=True), "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_svg_returns_svg():
    data = render_static(_sample(), _one_panel(x_eng=True, y_eng=True), "svg")
    assert b"<svg" in data[:512]


def test_render_two_panels_png():
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("上", True, False), PanelSpec("下", True, True)],
                     {"gain": 0, "phase": 1})
    data = render_static(_sample(), spec, "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_log_axis_png():
    spec = _one_panel(x_eng=True, y_eng=True, x_log=True, y_log=True)
    data = render_static(_sample(), spec, "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_rendering.py -k render -v`
Expected: FAIL（`render_static` 旧签名）

- [ ] **Step 3: 写实现**

替换 `app/rendering.py` 中 `render_static`：

```python
def render_static(parsed, spec, fmt):
    col_values = dict(zip(parsed.y_labels, parsed.ys))
    n = len(spec.panels)
    fig, axes = plt.subplots(n, 1, figsize=(8, max(3, 2.6 * n)), sharex=True, squeeze=False)
    axes = [row[0] for row in axes]
    try:
        for idx, panel in enumerate(spec.panels):
            ax = axes[idx]
            for col, i in spec.assign.items():
                if i == idx:
                    ax.plot(parsed.x, col_values[col], label=col)
            ax.set_ylabel(panel.y_title)
            ax.legend()
            if panel.y_log:
                ax.set_yscale("log")
            yf = _formatter(panel.y_eng)
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos, f=yf: f(v)))
        axes[0].set_title(spec.title)
        bottom = axes[-1]
        bottom.set_xlabel(spec.x_title)
        if spec.x_log:
            bottom.set_xscale("log")
        xf = _formatter(spec.x_eng)
        bottom.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: xf(v)))
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, bbox_inches="tight")
        return buf.getvalue()
    finally:
        plt.close(fig)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_rendering.py -v`
Expected: PASS（整个文件）

- [ ] **Step 5: 提交**

```bash
git add app/rendering.py tests/test_rendering.py
git commit -m "render_static 改吃 ChartSpec 多面板堆叠出图（issue 11）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `storage.py` 干净 schema 承载 `ChartSpec`

**Files:**
- Modify: `app/storage.py`
- Test: `tests/test_storage.py`

> 本任务后 `tests/test_storage.py` 全绿；`test_routes.py` 仍暂红（Task 6 恢复）。

**Interfaces:**
- Consumes: `app.spec.ChartSpec`
- Produces:
  - `Chart(id: str, title: str, created_at: str, spec: ChartSpec)`（dataclass）
  - `Storage.save_chart(chart_id: str, spec: ChartSpec, csv_bytes: bytes) -> Chart`
  - `Storage.get_chart(chart_id: str) -> Chart | None`（`.spec` 为 `ChartSpec`）
  - 其余方法（`exists`、`list_charts`、`read_csv`、`csv_path`、`cache_path`）签名不变

- [ ] **Step 1: 改写测试**

替换 `tests/test_storage.py`：

```python
from app.spec import ChartSpec, PanelSpec
from app.storage import Chart, Storage


def _spec(title="标题") -> ChartSpec:
    return ChartSpec(title, "X", True, False,
                     [PanelSpec("Y", True, False)], {"gain": 0})


def test_save_and_get(tmp_path):
    store = Storage(tmp_path)
    chart = store.save_chart("abc123xyz0", _spec(), b"x,gain\n1k,3.3\n")
    assert isinstance(chart, Chart)
    assert chart.id == "abc123xyz0"
    assert chart.spec.panels[0].y_title == "Y"

    fetched = store.get_chart("abc123xyz0")
    assert fetched is not None
    assert fetched.title == "标题"
    assert fetched.spec == _spec()
    assert store.read_csv("abc123xyz0") == b"x,gain\n1k,3.3\n"


def test_get_missing_returns_none(tmp_path):
    assert Storage(tmp_path).get_chart("nope") is None


def test_exists(tmp_path):
    store = Storage(tmp_path)
    assert store.exists("abc") is False
    store.save_chart("abc", _spec(), b"x,gain\n1k,3.3\n")
    assert store.exists("abc") is True


def test_list_charts_desc(tmp_path):
    store = Storage(tmp_path)
    store.save_chart("id1", _spec("first"), b"x,gain\n1k,3.3\n")
    store.save_chart("id2", _spec("second"), b"x,gain\n1k,3.3\n")
    assert [c.id for c in store.list_charts()] == ["id2", "id1"]


def test_persistence_across_instances(tmp_path):
    Storage(tmp_path).save_chart("keep", _spec(), b"x,gain\n1k,3.3\n")
    assert Storage(tmp_path).get_chart("keep") is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_storage.py -v`
Expected: FAIL（`save_chart` 旧签名 / `Chart` 旧字段）

- [ ] **Step 3: 写实现**

替换 `app/storage.py` 中 `Chart`、`_init_db`、`save_chart`、`_row_to_chart`、`get_chart`、`list_charts`（其余不变）：

```python
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.spec import ChartSpec


@dataclass
class Chart:
    id: str
    title: str
    created_at: str
    spec: ChartSpec


class Storage:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.csv_dir = self.data_dir / "csv"
        self.cache_dir = self.data_dir / "cache"
        self.db_path = self.data_dir / "plotpin.db"
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS charts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    spec_json TEXT NOT NULL
                )
                """
            )

    def csv_path(self, chart_id: str) -> Path:
        return self.csv_dir / f"{chart_id}.csv"

    def cache_path(self, chart_id: str, ext: str) -> Path:
        return self.cache_dir / f"{chart_id}.{ext}"

    def exists(self, chart_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM charts WHERE id = ?", (chart_id,)).fetchone()
            return row is not None

    def save_chart(self, chart_id: str, spec: ChartSpec, csv_bytes: bytes) -> Chart:
        created_at = datetime.now(timezone.utc).isoformat()
        self.csv_path(chart_id).write_bytes(csv_bytes)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO charts (id, title, created_at, spec_json) VALUES (?, ?, ?, ?)",
                (chart_id, spec.title, created_at, spec.to_json()),
            )
        return Chart(chart_id, spec.title, created_at, spec)

    def _row_to_chart(self, row: sqlite3.Row) -> Chart:
        return Chart(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            spec=ChartSpec.from_json(row["spec_json"]),
        )

    def get_chart(self, chart_id: str) -> Chart | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM charts WHERE id = ?", (chart_id,)).fetchone()
            return self._row_to_chart(row) if row else None

    def list_charts(self) -> list[Chart]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM charts ORDER BY created_at DESC, id DESC"
            ).fetchall()
            return [self._row_to_chart(r) for r in rows]

    def read_csv(self, chart_id: str) -> bytes:
        return self.csv_path(chart_id).read_bytes()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/storage.py tests/test_storage.py
git commit -m "storage 干净 schema 承载 ChartSpec（issue 11）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `main.py` 路由组装/读取 `ChartSpec`（恢复全绿）

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_routes.py`

> 本任务结束后**完整 `pytest` 全绿**恢复。

**Interfaces:**
- Consumes: `app.spec.ChartSpec`、`app.spec.PanelSpec`、`app.spec.validate_spec`、`app.storage.Chart`、`app.rendering.build_plotly_spec`、`app.rendering.render_static`、`app.parsing.read_csv_bytes`、`app.parsing.CSVParseError`
- Produces:
  - `POST /charts`：表单字段 `file`、`title`、`x_title`、`x_eng`（默认 False）、`x_log`（默认 False）、`layout`（JSON 字符串）。成功 303 到 `/chart/{id}`，失败 400 + `index.html` 回显
  - `layout` JSON 形如 `{"panels":[{"y_title","y_eng","y_log"}...],"assign":{"列名":面板号|null}}`
  - `GET /chart/{id}`、`/chart/{id}.png`、`/chart/{id}.svg` 用 `chart.spec`

- [ ] **Step 1: 改写测试**

替换 `tests/test_routes.py` 的上传辅助与相关用例（其余结构性测试保留）：

```python
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_storage
from app.storage import Storage


@pytest.fixture()
def client(tmp_path):
    store = Storage(tmp_path)
    app.dependency_overrides[get_storage] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _layout(panels, assign):
    return json.dumps({"panels": panels, "assign": assign})


def _upload(client, csv_text, layout=None):
    if layout is None:
        layout = _layout(
            [{"y_title": "Y", "y_eng": True, "y_log": False}],
            {"y": 0},
        )
    return client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "x_eng": "on", "layout": layout},
        files={"file": ("data.csv", csv_text.encode("utf-8"), "text/csv")},
        follow_redirects=False,
    )


def test_index_empty(client):
    assert client.get("/").status_code == 200


def test_upload_success_redirects(client):
    resp = _upload(client, "x,y\n1000,3.3\n2000,6.6\n")
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/chart/")


def test_upload_two_panels(client):
    layout = _layout(
        [{"y_title": "上", "y_eng": True, "y_log": False},
         {"y_title": "下", "y_eng": True, "y_log": False}],
        {"a": 0, "b": 1},
    )
    resp = _upload(client, "x,a,b\n1000,3.3,0.1\n2000,6.6,0.2\n", layout)
    assert resp.status_code == 303


def test_upload_bad_cell_shows_error(client):
    resp = _upload(client, "x,y\n1000,47x\n")
    assert resp.status_code == 400
    assert "47x" in resp.text


def test_upload_all_hidden_rejected(client):
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": False}], {"y": None})
    resp = _upload(client, "x,y\n1000,3.3\n2000,6.6\n", layout)
    assert resp.status_code == 400


def test_upload_bad_layout_json(client):
    resp = _upload(client, "x,y\n1000,3.3\n", layout="{not json")
    assert resp.status_code == 400


def test_chart_page_and_listing(client):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    assert client.get(f"/chart/{chart_id}").status_code == 200
    assert chart_id in client.get("/").text


def test_chart_not_found(client):
    assert client.get("/chart/missing").status_code == 404


def test_chart_page_has_http_copy_fallback(client):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    assert "execCommand" in client.get(f"/chart/{chart_id}").text


def test_png_render_and_cache(client, tmp_path):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    resp = client.get(f"/chart/{chart_id}.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert (tmp_path / "cache" / f"{chart_id}.png").exists()


def test_upload_log_with_nonpositive_rejected(client):
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": False}], {"y": 0})
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "x_log": "on", "layout": layout},
        files={"file": ("data.csv", b"x,y\n0,3.3\n1000,6.6\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "对数" in resp.text


def test_svg_render(client):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    resp = client.get(f"/chart/{chart_id}.svg")
    assert resp.status_code == 200
    assert "image/svg" in resp.headers["content-type"]


def test_index_thumbnail_only_when_cached(client):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    assert f'src="/chart/{chart_id}.png"' not in client.get("/").text
    client.get(f"/chart/{chart_id}.png")
    assert f'src="/chart/{chart_id}.png"' in client.get("/").text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_routes.py -v`
Expected: FAIL（旧路由签名 / 旧渲染调用 / 导入错误）

- [ ] **Step 3: 写实现**

替换 `app/main.py` 的导入、`create_chart`、`_image`、`chart_page`，并新增 `_build_spec`：

```python
import json
import os

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.ids import new_id
from app.parsing import CSVParseError, read_csv_bytes
from app.rendering import build_plotly_spec, render_static
from app.spec import ChartSpec, PanelSpec, validate_spec
from app.storage import Storage

app = FastAPI(title="PlotPin")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = Storage(os.environ.get("PLOTPIN_DATA_DIR", "data"))
    return _storage


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


def _index_items(store: Storage) -> list[dict]:
    return [
        {
            "chart": c,
            "thumb": f"/chart/{c.id}.png" if store.cache_path(c.id, "png").exists() else None,
        }
        for c in store.list_charts()
    ]


@app.get("/", response_class=HTMLResponse)
def index(request: Request, store: Storage = Depends(get_storage)):
    return templates.TemplateResponse(request, "index.html", {"items": _index_items(store)})


def _build_spec(title: str, x_title: str, x_eng: bool, x_log: bool, layout_json: str) -> ChartSpec:
    try:
        d = json.loads(layout_json)
        panels = [
            PanelSpec(p["y_title"], bool(p.get("y_eng")), bool(p.get("y_log")))
            for p in d["panels"]
        ]
        assign = {k: (None if v is None else int(v)) for k, v in d["assign"].items()}
    except (ValueError, KeyError, TypeError):
        raise CSVParseError("面板配置无法解析")
    return ChartSpec(title, x_title, bool(x_eng), bool(x_log), panels, assign)


@app.post("/charts")
async def create_chart(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    x_title: str = Form(...),
    x_eng: bool = Form(False),
    x_log: bool = Form(False),
    layout: str = Form(...),
    store: Storage = Depends(get_storage),
):
    raw = await file.read()
    try:
        parsed = read_csv_bytes(raw)
        spec = _build_spec(title, x_title, x_eng, x_log, layout)
        validate_spec(spec, parsed)
    except CSVParseError as err:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"items": _index_items(store), "error": str(err)},
            status_code=400,
        )
    chart_id = new_id()
    while store.exists(chart_id):
        chart_id = new_id()
    store.save_chart(chart_id, spec, raw)
    return RedirectResponse(url=f"/chart/{chart_id}", status_code=303)


@app.get("/chart/{chart_id}.png")
def chart_png(chart_id: str, store: Storage = Depends(get_storage)):
    return _image(chart_id, "png", "image/png", store)


@app.get("/chart/{chart_id}.svg")
def chart_svg(chart_id: str, store: Storage = Depends(get_storage)):
    return _image(chart_id, "svg", "image/svg+xml", store)


def _image(chart_id: str, ext: str, media_type: str, store: Storage) -> Response:
    chart = store.get_chart(chart_id)
    if chart is None:
        return _not_found_plain()
    cache = store.cache_path(chart_id, ext)
    if cache.exists():
        return Response(content=cache.read_bytes(), media_type=media_type)
    parsed = read_csv_bytes(store.read_csv(chart_id))
    data = render_static(parsed, chart.spec, ext)
    cache.write_bytes(data)
    return Response(content=data, media_type=media_type)


@app.get("/chart/{chart_id}", response_class=HTMLResponse)
def chart_page(chart_id: str, request: Request, store: Storage = Depends(get_storage)):
    chart = store.get_chart(chart_id)
    if chart is None:
        return templates.TemplateResponse(request, "404.html", {}, status_code=404)
    parsed = read_csv_bytes(store.read_csv(chart_id))
    spec = build_plotly_spec(parsed, chart.spec)
    return templates.TemplateResponse(
        request,
        "chart.html",
        {"chart": chart, "spec_json": json.dumps(spec)},
    )


def _not_found_plain() -> Response:
    return Response(content="404", media_type="text/plain", status_code=404)
```

- [ ] **Step 4: 运行全套测试确认通过**

Run: `pytest -v`
Expected: PASS（全部，含 spec / rendering / storage / routes / 既有 smoke 等）

- [ ] **Step 5: 提交**

```bash
git add app/main.py tests/test_routes.py
git commit -m "路由组装/读取 ChartSpec，恢复全绿（issue 11）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: 前端构建器（表头读列 + 面板分配 UI + layout JSON）

**Files:**
- Modify: `templates/index.html`
- Create: `static/builder.js`
- Test: 手动验证 + 既有 `tests/test_routes.py` 仍全绿

> 改前端做视觉/UI 设计时，按项目规则启用 `frontend-design` skill（`claude-plugins-official` 插件）；不可用时按其设计原则手工实现，不阻塞进度。沿用现有 `app.css` 的类名与视觉风格。

**Interfaces:**
- Consumes: `POST /charts` 期望的表单字段（`title`、`x_title`、`x_eng`、`x_log`、`layout`、`file`）
- Produces: 表单提交时隐藏字段 `layout` 的值为 `{"panels":[...],"assign":{...}}` JSON

- [ ] **Step 1: 改 `templates/index.html`**

把表单 `#config` 区的「Y 轴标题 / Y 轴卡片」替换为「面板构建器容器 + 隐藏 layout 字段」，保留 title 与 X 轴卡片。关键改动：

1. 删除 `<input name="y_title">` 整个 `.field`、删除 Y 轴 `.axiscard`（`y_eng`/`y_log`）。
2. 删除 X 轴卡片里无需改动；保留 `x_eng`（checked）与 `x_log`。
3. 在 `.m-body` 末尾、`.axes` 之后加入：

```html
<div class="field">
  <div class="ax">面板分配</div>
  <div id="builder" class="builder">
    <!-- builder.js 注入：面板数 +/-、每曲线下拉、每面板 Y 配置 -->
    <p class="hint" id="builder-hint">选择 CSV 文件后，这里可分配每条曲线到面板。</p>
  </div>
  <input type="hidden" name="layout" id="layout">
</div>
```

4. 表单底部脚本引用从 `upload.js` 改为 `builder.js`：

```html
<script src="/static/builder.js"></script>
<script src="/static/localtime.js"></script>
```

- [ ] **Step 2: 写 `static/builder.js`**

```javascript
// 读 CSV 首行表头 → 生成面板分配 UI → 提交前拼出 layout JSON。
// 无 JS / 读表头失败时优雅降级为「单面板、全部曲线」。
const fileInput = document.getElementById("file");
const config = document.getElementById("config");
const fileLabel = document.getElementById("file-label");
const builder = document.getElementById("builder");
const hint = document.getElementById("builder-hint");
const layoutField = document.getElementById("layout");
const form = document.getElementById("upload-form");

let columns = [];      // Y 列名（首行去掉第一列）
let panelCount = 1;

function readHeader(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => {
      const firstLine = String(reader.result).split(/\r?\n/)[0] || "";
      const cells = firstLine.split(",").map((s) => s.trim());
      resolve(cells.slice(1)); // 第一列是 X
    };
    reader.onerror = () => resolve([]);
    reader.readAsText(file.slice(0, 64 * 1024)); // 只读前 64KB 足够拿表头
  });
}

function render() {
  if (!columns.length) {
    builder.innerHTML = '<p class="hint">未能读取列名，将按单面板（全部曲线）生成。</p>';
    return;
  }
  let html = '<div class="panel-count">面板数：' +
    '<button type="button" class="pc-dec">−</button>' +
    '<span class="pc-val">' + panelCount + "</span>" +
    '<button type="button" class="pc-inc">+</button></div>';

  html += '<table class="assign"><thead><tr><th>曲线</th><th>分配</th></tr></thead><tbody>';
  for (const col of columns) {
    html += '<tr><td>' + escapeHtml(col) + '</td><td><select data-col="' + escapeHtml(col) + '">';
    for (let i = 0; i < panelCount; i++) {
      html += '<option value="' + i + '">面板' + (i + 1) + "</option>";
    }
    html += '<option value="hidden">不显示</option></select></td></tr>';
  }
  html += "</tbody></table>";

  html += '<div class="panel-cfgs">';
  for (let i = 0; i < panelCount; i++) {
    html += '<div class="panel-cfg" data-panel="' + i + '">' +
      '<div class="ax">面板' + (i + 1) + ' Y 轴</div>' +
      '<input type="text" class="p-title" placeholder="Y 轴标题">' +
      '<label><input type="checkbox" class="p-eng" checked> 工程计数法</label>' +
      '<label><input type="checkbox" class="p-log"> 对数坐标</label></div>';
  }
  html += "</div>";

  builder.innerHTML = html;
  builder.querySelector(".pc-dec").addEventListener("click", () => {
    if (panelCount > 1) { panelCount--; render(); }
  });
  builder.querySelector(".pc-inc").addEventListener("click", () => {
    panelCount++; render();
  });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function buildLayout() {
  // 降级：无列名时单面板、全部曲线归面板 0
  if (!columns.length) {
    return { panels: [{ y_title: "Y", y_eng: true, y_log: false }], assign: {} };
  }
  const assign = {};
  builder.querySelectorAll("select[data-col]").forEach((sel) => {
    const v = sel.value;
    assign[sel.dataset.col] = v === "hidden" ? null : parseInt(v, 10);
  });
  const panels = [];
  builder.querySelectorAll(".panel-cfg").forEach((cfg) => {
    panels.push({
      y_title: cfg.querySelector(".p-title").value || "Y",
      y_eng: cfg.querySelector(".p-eng").checked,
      y_log: cfg.querySelector(".p-log").checked,
    });
  });
  return { panels, assign };
}

if (fileInput && config) {
  fileInput.addEventListener("change", async () => {
    config.hidden = !fileInput.files.length;
    if (fileInput.files.length) {
      if (fileLabel) fileLabel.textContent = "▤ " + fileInput.files[0].name;
      columns = await readHeader(fileInput.files[0]);
      panelCount = 1;
      render();
    }
  });

  const intake = document.querySelector(".intake");
  if (intake) {
    intake.addEventListener("click", (e) => {
      if (e.target.closest(".pick")) return;
      fileInput.click();
    });
  }
}

if (form) {
  form.addEventListener("submit", () => {
    layoutField.value = JSON.stringify(buildLayout());
  });
}
```

- [ ] **Step 3: 运行既有路由测试确认未破坏**

Run: `pytest tests/test_routes.py -v`
Expected: PASS（前端改动不影响后端契约；`index` 页仍 200）

- [ ] **Step 4: 手动验证**

```bash
PLOTPIN_DATA_DIR=$(mktemp -d) uvicorn app.main:app --port 8011 &
```

浏览器打开 `http://localhost:8011`：
1. 选一个含 `x,a,b,c` 的 CSV → 出现面板数控件与 3 个曲线下拉。
2. 面板数 +1 → 下拉多出「面板2」选项、下方多出「面板2 Y 轴」配置块。
3. 把 a→面板1、b→面板2、c→不显示，各面板填 Y 标题 → 生成图表。
4. 跳转后页面应显示 2 个堆叠面板、c 不出现；`.png` / `.svg` 链接可打开且为多面板图。
5. 关闭：`kill %1`。

- [ ] **Step 5: 提交**

```bash
git add templates/index.html static/builder.js
git commit -m "前端面板分配构建器，提交拼 layout JSON（issue 11）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: 展示页绘图容器高度按面板数自适应

**Files:**
- Modify: `templates/chart.html`
- Test: 手动验证 + 既有 `tests/test_routes.py` 仍全绿

**Interfaces:**
- Consumes: 模板上下文 `chart`（含 `chart.spec.panels`）、`spec_json`

- [ ] **Step 1: 改 `templates/chart.html`**

把固定高度 `#plot`（当前 `height:420px`）改为按面板数计算高度。将 `#plot` 的内联高度去掉，改由脚本设置：

```html
<div class="panel">
  <div id="plot" style="width:100%;"></div>
</div>
```

在初始化脚本中，依据 layout 内 `yaxis*` 的数量设定高度（每面板 ~300px，最小 360px）：

```javascript
const spec = JSON.parse(document.getElementById("spec").textContent);
const panelN = Object.keys(spec.layout).filter((k) => /^yaxis\d*$/.test(k)).length || 1;
document.getElementById("plot").style.height = Math.max(360, panelN * 300) + "px";
Plotly.newPlot("plot", spec.data, spec.layout, {responsive: true});
```

（其余复制按钮 / 链接脚本不变。）

- [ ] **Step 2: 运行既有路由测试确认未破坏**

Run: `pytest tests/test_routes.py -v`
Expected: PASS

- [ ] **Step 3: 手动验证**

复用 Task 7 启动的服务（或重新启动）：打开一个 2 面板分享页，确认两个面板纵向堆叠、各自 Y 轴刻度独立、共享底部 X 轴、整体高度随面板数增大；单面板分享页高度正常。

- [ ] **Step 4: 提交**

```bash
git add templates/chart.html
git commit -m "展示页绘图高度按面板数自适应（issue 11）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: 全量回归与收尾

**Files:**
- Test: 全套 `pytest`

- [ ] **Step 1: 跑全套测试**

Run: `pytest -v`
Expected: PASS（全部）

- [ ] **Step 2: 端到端冒烟**

```bash
PLOTPIN_DATA_DIR=$(mktemp -d) uvicorn app.main:app --port 8012 &
```
上传一个多列 CSV → 多面板分配 → 校验页面 / PNG / SVG 三个链接均正确呈现多面板。`kill %1`。

- [ ] **Step 3: 删除已无人调用的 `check_log_positivity` 及其测试**

`validate_spec` 已接管 X 轴对数与每面板对数校验，`app/parsing.py` 的 `check_log_positivity` 成为死代码，路由也不再 import 它。删除：

1. `app/parsing.py`：删除 `check_log_positivity` 函数（文件末尾 `def check_log_positivity(...)` 整段）。
2. `tests/test_parsing.py`：删除 `_parsed()` 助手与 4 个 log 测试（约第 58–86 行：`def _parsed()` 起，到 `test_no_check_when_log_off` 结束）。

确认无其他残留引用：

Run: `grep -rn "check_log_positivity" app/ tests/`
Expected: 无任何输出。

- [ ] **Step 4: 跑全套测试确认仍全绿**

Run: `pytest -v`
Expected: PASS（全部）

- [ ] **Step 5: 最终提交**

```bash
git add -A
git commit -m "清理旧单轴遗留 check_log_positivity（issue 11）

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
