# 多 Y 轴数据自由分配（多面板）设计

> Issue #11。一个分享页可以包含多个上下堆叠的独立面板，用户在创建时自由地把每条曲线（Y 列）指派到某个面板。
>
> 范围说明：本 spec 只覆盖 Issue #11。Issue #10（开放 API）将基于本设计确定的 `ChartSpec` 模型，另出独立 spec → plan → 实现。

## 目标与背景

当前模型：一个 chart = 一个 CSV + 一组扁平配置（title、x/y 标题、x/y 工程计数、x/y 对数），**所有 Y 列画在同一坐标系、同一张图**。当多条曲线量纲差异很大时，挤在一个 Y 轴上无法看清。

本特性让用户在创建时：

- 指定**面板数**（+/- 增减）；
- 为每条曲线选择它属于**哪个面板**，或**不显示**；
- 为**每个面板**单独配置 Y 轴（y 标题 / 工程计数法 / 对数）。

最终一个分享页呈现为**纵向堆叠、共享 X 轴**的多个面板，永久链接（页面 / PNG / SVG）语义不变。

### 关键约束

- 项目尚未正式上线，**无需兼容老数据**，可以采用干净 schema，优先实现效果。
- 永久不变：分享 id 与其页面 / PNG / SVG 链接的语义不变，缓存策略不变。
- 架构三层不变：纯逻辑（零 Web/DB 依赖，测试重点）→ 数据访问 → 薄路由。依赖只能从外往里指。
- 所有展示给用户的时间仍遵循「后端 UTC、前端转本地时间」规则，本特性不引入新的时间展示。

### 非目标（YAGNI）

- 不做同一绘图区叠加多 Y 轴（次坐标轴）模式——只做堆叠独立面板。
- 不做拖拽分配 UI——用下拉框。
- 不允许一条曲线出现在多个面板——每条曲线恰好属于一个面板或不显示。
- 不做创建后编辑分享（分享不可变）。
- 不在本 spec 内实现开放 API（Issue #10）。

## 决策摘要

| 决策点 | 选定 |
|---|---|
| 布局形态 | 上下堆叠的独立面板，共享 X 轴 |
| 分配交互 | 每条曲线一个下拉（面板1 / 面板2 / … / 不显示），面板数 +/- 增减 |
| X 轴配置 | 页面级共享一套（x 标题 / 工程计数 / 对数） |
| Y 轴配置 | 每个面板独立（y 标题 / 工程计数 / 对数） |
| 存储 | 干净 schema，`ChartSpec` 序列化为 `spec_json` |
| 静态出图 | 多面板渲染成**一张**纵向堆叠子图的 PNG/SVG |
| 创建流程 | 前端 JS 只读 CSV 首行表头生成下拉；完整解析/校验在提交时由后端做 |
| 向后兼容 | 不需要（项目未上线） |

## 数据模型

新增纯逻辑模块 `app/spec.py`（纯逻辑层最内层，零 Web/DB 依赖）：

```python
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
    panels: list[PanelSpec]          # 有序，面板1 == panels[0]
    assign: dict[str, int | None]    # 列名 → 面板下标；None == 不显示
```

职责：

- `ChartSpec.to_json() -> str` / `ChartSpec.from_json(s: str) -> ChartSpec`：序列化往返，存取 `spec_json`。
- `validate_spec(spec: ChartSpec, parsed: ParsedCSV) -> None`：失败时抛 `CSVParseError`（复用现有异常，路由层统一处理）。校验项：
  - `panels` 非空；
  - `assign` 的每个面板下标在 `[0, len(panels))` 内，或为 `None`；
  - `assign` 的键集合与 `parsed.y_labels` 一致（不多不少）；
  - 至少一个面板含有至少一条可见曲线（不能整页全部「不显示」）；
  - 对每个**对数面板**，其归属曲线的所有值 > 0（按面板分别校验，替换现有全局 `check_log_positivity`）；
  - 对 X 轴对数：`parsed.x` 全部 > 0（保留现有逻辑，移入此处）。

依赖方向：`spec.py` 仅依赖 `parsing.py`（用其 `ParsedCSV`、`CSVParseError` 类型），不反向依赖。

## 存储（`app/storage.py`）

干净 schema，丢弃旧的扁平列：

```sql
CREATE TABLE IF NOT EXISTS charts (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    spec_json  TEXT NOT NULL
);
```

- `title`、`created_at` 留列，供首页列表无需解析 JSON 即可展示。
- `spec_json` 存完整 `ChartSpec`（含 title 冗余、x 配置、panels、assign）。
- `Chart` dataclass 简化为 `id`、`title`、`created_at`、`spec`（`ChartSpec` 实例），由 `_row_to_chart` 读出 `spec_json` 后 `from_json` 得到。
- `save_chart(chart_id, spec: ChartSpec, csv_bytes)`：写 CSV 文件、插入 `(id, spec.title, created_at, spec.to_json())`。
- CSV 原文仍以 `{id}.csv` 落盘，缓存仍以 `{id}.png` / `{id}.svg` 落盘，路径与语义不变。

读取统一为**单一路径**：`get_chart` → `Chart`（内含 `ChartSpec`），无新旧分支。

## 路由（`app/main.py`，保持薄）

### `POST /charts`

表单字段：

- `file`：CSV 文件（同现在）。
- `title`、`x_title`、`x_eng`、`x_log`：页面级标量。
- `layout`：JSON 字符串，前端拼好的 `{"panels": [{"y_title","y_eng","y_log"}...], "assign": {"列名": 面板号|null}}`。

路由职责（薄）：

1. `read_csv_bytes(raw)` 解析（逐格数值校验，沿用现有）。
2. 解析 `layout` JSON，组装出 `ChartSpec`（含页面级 x 配置 + 解析出的 panels/assign）。
3. `validate_spec(spec, parsed)`。
4. 生成不冲突的 `chart_id`，`store.save_chart(chart_id, spec, raw)`。
5. 成功 → 303 重定向到 `/chart/{id}`。

失败处理：`CSVParseError`（编码 / 格式 / 数值 / 对数冲突 / 分配非法）或 `layout` JSON 解析失败 → 400 + 在 `index.html` 回显错误信息（沿用现有错误回显机制）。

### `GET /chart/{id}`、`/chart/{id}.png`、`/chart/{id}.svg`

- 统一先 `store.get_chart(id)` 得到 `Chart`（含 `spec`）。
- `chart_page`：`build_plotly_spec(parsed, spec)` → 渲染 `chart.html`。
- `_image`：缓存命中直接返回；否则 `render_static(parsed, spec, ext)` → 写缓存 → 返回。
- 三个出口共用同一个 `spec` 来源；`id` 不存在仍走现有 404 路径。

## 渲染层（`app/rendering.py`，纯逻辑，测试重点）

两个函数签名从「一长串扁平标量」改为「`(parsed, spec: ChartSpec)`」。

### `build_plotly_spec(parsed, spec)`

- 按 `spec.assign` 把每条曲线归到面板；`None`（不显示）跳过。
- 生成 Plotly **纵向堆叠多子图**：N 个面板对应 `yaxis`、`yaxis2`…`yaxisN`，共享 X 轴（各面板 trace 绑定到对应 `yaxis{n}`，X 轴 domain 共用、刻度全局共享）。
- 每个面板：tickvals/ticktext 按该面板 `y_eng` 用现有 `format_eng`/`format_plain`，`type: "log"` 按该面板 `y_log`，y 标题取该面板 `y_title`。
- X 轴刻度按 `spec.x_eng` / `spec.x_log` 全局生成一次。
- `hovertemplate` 沿用现有工程计数法显示风格。
- 退化：N==1 时即单面板，行为与今天的单图一致。

### `render_static(parsed, spec, fmt)`

- `plt.subplots(len(spec.panels), 1, sharex=True)` 纵向堆叠；`len==1` 时为单 ax。
- 每个 `ax` 画归属本面板的曲线、设 y 标题、`set_yscale("log")`（若该面板 log）、y 轴 `FuncFormatter`（按该面板 eng）。
- 最末 ax 设共享 x 标题；x 轴 log / formatter 按页面级配置。
- 各面板 `legend()` 仅含本面板曲线。
- 输出仍是**单张** PNG / SVG（`fig.savefig`，`bbox_inches="tight"`）。
- 「不显示」的列两边都跳过；空面板已被 `validate_spec` 排除。

CJK 字体处理逻辑不变。

## 前端（`templates/`、`static/`）

改前端做视觉 / UI 设计时，按项目规则启用 `frontend-design` skill（`claude-plugins-official` 插件）；不可用时按其设计原则手工实现，不阻塞进度。

### 创建页（`templates/index.html` + 新增 `static/builder.js`）

- 用户选定 CSV 文件后，`builder.js` 用 `FileReader` 只读**首行表头**（不做数值解析）得到列名。
- 渲染分配构建器：
  - 「面板数」+/- 控件（默认 1）。
  - 每条曲线一行，行尾一个下拉：`面板1 / 面板2 / … / 不显示`。
  - 每个面板一个配置块：y 标题输入、工程计数勾选、对数勾选。
  - 页面级：title、x 标题、x 工程计数、x 对数。
- 提交前把面板配置 + 分配拼成 `layout` JSON 写入隐藏字段，连同 CSV 与页面级字段一起 `POST /charts`。
- **创建需启用 JavaScript**：面板分配 UI 与 `layout` JSON 均由 `builder.js` 生成；无 JS 或表头读取失败时无法提交有效 `layout`，后端会以 400 拒绝（不做服务端兜底）。本特性不提供无 JS 降级——这是经确认的取舍（决策见 SDD 进度账本 [T7]）。

### 展示页（`templates/chart.html`）

- 现有单一 `#plot` 容器继续使用——Plotly 多子图渲染进同一个 div。
- 高度按面板数自适应（每面板给定一个最小高度）。
- 永久链接区（页面 / PNG / SVG + 复制按钮）不变。

## 错误处理

| 场景 | 处理 |
|---|---|
| CSV 编码 / 格式 / 数值非法 | `CSVParseError` → 400 + `index.html` 回显（现有） |
| 某对数面板含 ≤0 值 | `validate_spec` 抛 `CSVParseError`（按面板报） → 400 |
| X 轴对数含 ≤0 值 | `validate_spec` 抛 `CSVParseError` → 400 |
| 面板下标越界 / 分配键与列名不符 | `validate_spec` 抛 `CSVParseError` → 400 |
| 整页全部「不显示」 / 面板数为 0 | `validate_spec` 抛 `CSVParseError` → 400 |
| `layout` JSON 无法解析 | 400 + 回显 |
| 分享 id 不存在 | 现有 404 路径不变 |

## 测试（TDD，先写失败测试再实现）

重心在纯逻辑层（脱离 Web 与 DB 直接单测）。

### `tests/test_spec.py`（新增）

- `ChartSpec.to_json()`/`from_json()` 往返等价（含多面板、含 `None` 分配）。
- `validate_spec` 各分支：
  - 合法多面板通过；
  - 面板下标越界 → 抛错；
  - `assign` 键与 `y_labels` 不一致 → 抛错；
  - 整页全部隐藏 / `panels` 为空 → 抛错；
  - 某对数面板含 ≤0 值 → 抛错；其他非对数面板含 ≤0 值不报错；
  - X 轴对数含 ≤0 值 → 抛错。

### `tests/test_rendering.py`（扩充）

- 多面板 `build_plotly_spec`：生成正确数量的 `yaxis{N}`，曲线按 `assign` 绑定到正确 `yaxis`；「不显示」列不出现在 traces。
- 每面板独立 eng/log 反映到对应轴的 ticktext / type。
- `render_static` 多面板：PNG 与 SVG 均能出图、字节非空。
- 单面板退化（N==1）：plotly spec 与静态图都能正常生成。

### `tests/test_main.py`（扩充）

- `POST /charts` 带合法 `layout` JSON → 303，且落库可由 `GET` 读回。
- `POST /charts` 带非法 `layout`（越界 / 全隐藏 / 坏 JSON）→ 400 且错误回显。
- `GET /chart/{id}`、`.png`、`.svg` 对多面板分享均正常返回。

## 实现顺序建议

1. `app/spec.py` + `tests/test_spec.py`（纯逻辑，先行）。
2. `app/rendering.py` 改签名吃 `ChartSpec` + 渲染测试。
3. `app/storage.py` 干净 schema + `save_chart`/`get_chart` 改造。
4. `app/main.py` 路由改造 + `tests/test_main.py`。
5. `templates/index.html` + `static/builder.js` 构建器 + `chart.html` 多子图高度自适应。
6. 端到端手测：上传多列 CSV → 分配多面板 → 校验页面 / PNG / SVG。
