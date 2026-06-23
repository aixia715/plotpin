# 对数轴自动剔除 ≤0 值并警告（Issue 18）

## 背景与问题

当前上传含 ≤0 值的 CSV 并勾选对数坐标时，`app/parsing.py` 的 `check_log_positivity`
会直接抛 `CSVParseError` 拒绝上传。Issue 18 要求改为：**自动剔除对数轴上 ≤0 的部分照常出图，
并在图表页给出约 3 秒的警告**。

附带修掉一个真实 bug：去掉拒绝逻辑后，`rendering._ticks` 对 log 轴调用
`log_ticks(min, max)`，若边界 ≤0 会抛 `ValueError`。因此"剔除 ≤0"必须在算刻度前完成。

## 已对齐的决策

1. **警告时机/位置**：图表页每次打开都显示约 3 秒的 toast（只要该图在对数轴上剔除过 ≤0 点）。
   警告状态由数据实时算出，不持久化，永久链接稳健。
2. **剔除粒度**：逐点剔除留缺口。X 对数轴 ≤0 删整行；Y 对数轴某曲线的 ≤0 点单独置空（断线缺口），
   不影响同一 X 处的其他曲线。
3. **全 ≤0 边界**：若某条对数轴剔除后没有任何正数可画 → 报错拒绝（沿用现有 `CSVParseError` → 400）。
4. **文案**：`对数 X 轴包含 ≤0 的值，已自动忽略` / `对数 Y 轴包含 ≤0 的值，已自动忽略` /
   `对数 X 轴和 Y 轴包含 ≤0 的值，已自动忽略`。

## 架构改动（三层，依赖只能从外往里指）

### 纯逻辑层 `app/parsing.py`

- `ParsedCSV.ys` 类型由 `list[list[float]]` 放宽为 `list[list[float | None]]`。
- 移除 `check_log_positivity`，新增：

  ```python
  @dataclass
  class LogFilterReport:
      x_dropped: bool
      y_dropped: bool

  def apply_log_filter(
      parsed: ParsedCSV, x_log: bool, y_log: bool
  ) -> tuple[ParsedCSV, LogFilterReport]: ...
  ```

  语义：
  - `x_log` 为真：删除所有 `x ≤ 0` 的行（x 与全部 y 按下标对齐删除）。若有删除则 `x_dropped=True`。
  - `y_log` 为真：在（可能已被 x 过滤后的）数据上，把每条曲线里 `y ≤ 0` 的点置为 `None`。
    若有任何置空则 `y_dropped=True`。
  - 全 ≤0 报错：
    - `x_log` 且过滤后 `x` 为空 → `raise CSVParseError("X 轴所有值 ≤0，无法使用对数坐标")`。
    - `y_log` 且全部曲线的全部 y 都被置空（无任何正数）→
      `raise CSVParseError("Y 轴所有值 ≤0，无法使用对数坐标")`。
      （只要存在至少一个正数 y 即可出图；个别曲线整条被置空是允许的。）
  - 非对数轴不动；对数轴但全为正数时不删、不报告。
  - 纯函数，无 Web/DB 依赖，是测试投入重点。

### 渲染层 `app/rendering.py`（依赖 parsing，方向正确）

让两个渲染器内部统一调用 `apply_log_filter`，保证三个入口行为一致：

- `_ticks(values, use_log)`：先 `[v for v in values if v is not None]` 再取 min/max。
  过滤保证对数轴有正数，`log_ticks` 不会再拿到 ≤0。
- `build_plotly_spec(...)`：
  - 开头 `parsed, report = apply_log_filter(parsed, x_log, y_log)`。
  - trace 的 `y` 直接含 `None`（Plotly 原生渲染为断线缺口）。
  - `customdata` 对 `None` 保护：`yf(yv) if yv is not None else None`。
  - 在返回 dict 增加警告文案字段，例如 `{"data": ..., "layout": ..., "warning": "<文案或 ''>"}`，
    供图表页传给模板。文案由 `report` 生成（见"文案"决策）。
- `render_static(...)`：
  - 开头同样 `apply_log_filter`。
  - 画图前 `None → float('nan')`（matplotlib 用 NaN 画缺口）。
  - 静态 PNG/SVG 无法弹 toast，仅静默剔除，不输出警告。

### 路由层 `app/main.py`

- `create_chart`：在 `try` 中 `read_csv_bytes` 后调用 `apply_log_filter(parsed, x_log, y_log)`
  做上传期校验（触发"全 ≤0 → 400"）。仍存储**原始** CSV，**不改存储 schema**。
- `chart_page`：从 `build_plotly_spec` 返回值取 `warning`，传给模板（如 `log_warning`）。
- `_image`：无需改动（`render_static` 内部已过滤）。

### 视图层 `templates/chart.html` + `static/app.css`

- 当 `log_warning` 非空时渲染一个 toast 元素，承载文案。
- 一小段 JS 让 toast 显示约 3 秒后淡出移除。
- toast 为新 UI 组件，实现时按项目约定启用 `frontend-design` skill 做视觉
  （取向、排版、组件取舍）。

### 存储 `app/storage.py`

无改动，无迁移。警告实时计算，不持久化。

## 测试计划（TDD，先写失败测试再实现）

### `tests/test_parsing.py`
- `x_log` 删除 ≤0 行、`x_dropped=True`，y 同步对齐删除。
- `y_log` 把某曲线 ≤0 点置 `None`、`y_dropped=True`，其他曲线/点不受影响。
- x、y 同时为对数时两类剔除都生效。
- 非对数：数据不变，`x_dropped=y_dropped=False`。
- 对数但全正：不删、不报告。
- `x_log` 全 ≤0 → 抛 `CSVParseError`。
- `y_log` 全部曲线全 ≤0 → 抛 `CSVParseError`。
- `y_log` 某曲线整条 ≤0 但另一曲线有正数 → 不抛，置空那条曲线。

### `tests/test_rendering.py`
- `_ticks` 忽略 `None`。
- `build_plotly_spec`：含 ≤0 + log 时 trace 的 y 含 `null`，`customdata` 不崩，返回 `warning` 文案正确。
- `render_static`：含缺口数据出图不崩。

### `tests/test_routes.py`
- 含 ≤0 + log 上传现在返回 303（原为 400）。
- 图表页 HTML 含警告文案。
- 全 ≤0 + log 上传仍返回 400。

## 影响面

- 行为变更：含 ≤0 + 对数从"拒绝上传"变为"剔除出图 + 警告"。
- API/路由签名不变；存储 schema 不变。
- `ParsedCSV.ys` 可能含 `None`，所有消费方（仅渲染层）已相应处理。
