# 对数轴自动剔除 ≤0 值并警告（Issue 18）

> 注：本 spec 已对齐 issue 11 之后的**多面板 `ChartSpec` 架构**（`app/spec.py`）。
> 早期草稿基于过时的单面板 `check_log_positivity`，已废弃重写。

## 背景与问题

当前架构（`app/spec.py`）：`ChartSpec`（含共享的 `x_log`、`panels`、`assign`）+ 每个 `PanelSpec`
各自的 `y_log`；曲线经 `assign`（列名→面板序号或 `None`）分配到面板。
`validate_spec(spec, parsed)` 在上传时校验，遇对数轴含 ≤0 直接抛 `CSVParseError` 拒绝上传
（x_log：`app/spec.py:66`；逐面板 y_log：`app/spec.py:69-74`）。

Issue 18 要求改为：**自动剔除对数轴上 ≤0 的部分照常出图，并在图表页给出约 3 秒警告**。

附带修掉一个真实 bug：去掉拒绝逻辑后，`rendering._ticks` 对 log 轴调用
`log_ticks(min, max)`，若边界 ≤0 会抛 `ValueError`。因此"剔除 ≤0"必须在算刻度前完成。

## 已对齐的决策

1. **警告时机/位置**：图表页每次打开都显示约 3 秒的 toast（只要该图在对数轴上剔除过 ≤0 点）。
   警告状态由数据实时算出，不持久化，永久链接稳健。
2. **剔除粒度**：逐点剔除留缺口。X 对数轴（共享）≤0 删整行；某 `y_log` 面板里、分配到它的列的
   ≤0 点单独置 `None`（断线缺口），不影响其他面板/曲线；分配到**非** log 面板的列保留 ≤0（线性轴合法）。
3. **全 ≤0 边界**：若某条对数轴剔除后没有任何正数可画 → 报错拒绝（沿用 `CSVParseError` → 400）。
4. **文案（多面板聚合，沿用已批准措辞）**：
   - 仅 X 轴剔除：`对数 X 轴包含 ≤0 的值，已自动忽略`
   - 仅某/某些 Y 面板剔除：`对数 Y 轴包含 ≤0 的值，已自动忽略`
   - 两者都有：`对数 X 轴和 Y 轴包含 ≤0 的值，已自动忽略`
   - 无剔除：空串 `""`
   - 多个 log 面板都剔除时仍用单条聚合文案（不逐面板列举），保持简洁。

## 架构改动（依赖方向 `rendering → spec → parsing → eng_notation`）

### 纯逻辑层 `app/spec.py`（新增过滤；改 validate_spec）

`ParsedCSV.ys` 元素在过滤后可能为 `None`（缺口）。新增：

```python
@dataclass
class LogFilterReport:
    x_dropped: bool = False
    y_dropped: bool = False


def apply_log_filter(
    parsed: ParsedCSV, spec: ChartSpec
) -> tuple[ParsedCSV, LogFilterReport]: ...
```

语义：
- `spec.x_log` 真：删除所有 `x ≤ 0` 的行（x 与所有列按下标对齐删除）。有删除则 `x_dropped=True`；
  删空 → `raise CSVParseError("X 轴所有值 ≤0，无法使用对数坐标")`。
- 对每个 `panel.y_log` 为真的面板：把**分配到该面板**的列里 `y ≤ 0` 的点置 `None`。
  有置空则 `y_dropped=True`；若该面板所有分配列都无任何正数 →
  `raise CSVParseError("面板 {i+1} 所有值 ≤0，无法使用对数坐标")`。
- 非 log 轴/面板不动；对数轴但全正数时不删、不报告。
- 返回过滤后的 `ParsedCSV` 与 `LogFilterReport`。纯函数，测试重点。

`validate_spec` 调整：
- **删除**现有 ≤0 拒绝逻辑（`app/spec.py:66-67` 与 `app/spec.py:68-74`）。
- 保留结构校验（面板非空、assign 一致、下标范围、非全隐藏、面板非空分配）。
- 在函数末尾追加 `apply_log_filter(parsed, spec)`（丢弃返回值），使"全 ≤0"仍在上传期触发 400。
  这样 `create_chart` 无需改动，业务规则单点收敛在 `apply_log_filter`。

### 渲染层 `app/rendering.py`（依赖 spec，方向正确）

让两个渲染器内部统一调用 `apply_log_filter`，保证三个入口（上传校验、交互页、PNG/SVG）一致：

- `_ticks(values, use_log)`：先 `[v for v in values if v is not None]` 再取 min/max。
  过滤保证对数轴有正数，`log_ticks` 不会再拿到 ≤0。
- 新增 `_log_warning_text(report) -> str`：按"文案"决策由 `report` 生成。
- `build_plotly_spec(parsed, spec)`：
  - 开头 `parsed, report = apply_log_filter(parsed, spec)`，之后基于过滤数据重建 `col_values`。
  - trace 的 `y` 含 `None`（Plotly 原生渲染为断线缺口）。
  - `customdata` 对 `None` 保护：`yf(yv) if yv is not None else None`。
  - 返回 dict 增加 `"warning"` 键：`{"data": ..., "layout": ..., "warning": "<文案或 ''>"}`。
- `render_static(parsed, spec, fmt)`：
  - 开头同样 `apply_log_filter`，基于过滤数据重建 `col_values`。
  - 画图前 `None → float('nan')`（matplotlib 用 NaN 画缺口）。
  - 静态 PNG/SVG 无法弹 toast，仅静默剔除，不输出警告。

### 路由层 `app/main.py`

- `create_chart`：**无需改动**——`validate_spec` 内部已通过 `apply_log_filter` 触发"全 ≤0 → 400"，
  部分 ≤0 不再报错，上传自然 303 成功。
- `chart_page`：从 `build_plotly_spec` 返回值取 `warning`，加入模板上下文
  `{"chart": chart, "spec": spec, "log_warning": spec["warning"]}`。
  （`spec` dict 里多出的 `"warning"` 键对 Plotly 无副作用，JS 只读 `data`/`layout`。）
- `_image`：无需改动（`render_static` 内部已过滤）。

### 视图层 `templates/chart.html` + `static/app.css`

- 当 `log_warning` 非空时渲染一个 toast 元素，承载文案。
- 一小段 JS 让 toast 显示约 3 秒后淡出移除。
- toast 为新 UI 组件，实现时按项目约定启用 `frontend-design` skill 做视觉。

### 存储 `app/storage.py`

无改动，无迁移。警告实时计算，不持久化。

## 测试计划（TDD，先写失败测试再实现）

### `tests/test_spec.py`
- 迁移 `test_validate_log_panel_with_nonpositive`：phase 含 -1 归入 log 面板，现应**不报错**（剔除），
  改为断言 `apply_log_filter` 把该点置 `None` 且 `y_dropped=True`。
- 迁移 `test_validate_x_log_nonpositive`：x 含 0，现应**不报错**（删行），改为断言删行与 `x_dropped=True`。
- 新增 `apply_log_filter`：x 删行、y 置空缺口、多面板（log 面板剔除 / 非 log 面板保留 ≤0）、
  全正不动、x 全 ≤0 抛错、log 面板所有列全 ≤0 抛错、面板某列全 ≤0 但另一列有正数不抛。
- 保留并仍通过：结构校验类测试、`test_validate_log_panel_positive_ok`（全正不抛）。

### `tests/test_rendering.py`
- `_ticks` 忽略 `None`。
- `build_plotly_spec`：log 面板含 ≤0 时对应 trace 的 y 含 `null`、`customdata` 不崩、
  返回 `warning` 文案正确；x_log 含 ≤0 时 x 删行且 `warning` 含 X；全正时 `warning == ""`。
- `render_static`：含缺口数据出图不崩。
- 现有全正 log 测试保持通过。

### `tests/test_routes.py`
- 迁移 `test_upload_log_with_nonpositive_rejected`：部分 ≤0 现返回 **303**（原 400）。
- 新增：图表页 HTML 含警告文案；x 全 ≤0 + x_log 仍返回 400。

## 影响面

- 行为变更：对数轴含 ≤0 从"拒绝上传"变为"剔除出图 + 警告"；全 ≤0 仍拒绝。
- API/路由签名不变；存储 schema 不变。
- `ParsedCSV.ys` 过滤后可能含 `None`，消费方（仅渲染层）已相应处理。
- 迁移既有测试：`test_spec.py` 2 条、`test_routes.py` 1 条语义翻转，避免回归。
