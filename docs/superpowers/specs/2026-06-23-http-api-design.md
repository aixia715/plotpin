# 设计：开放 HTTP API 接口给其他应用（issue #10）

## 目标

让其他应用以编程方式提交 CSV + 绘图配置，拿回该图表的分享页 / PNG / SVG / CSV 的**绝对 URL**。当前只有面向浏览器的表单端点 `POST /charts`（提交后 303 跳转到 HTML 页），不适合程序调用。

## 范围与约束

- 局域网自部署，**不鉴权**（与现有浏览器上传一致，局域网可信）。
- CSV 以 **multipart 文件上传** 方式传入（与现有端点一致，`curl -F` 即可调用）。
- 返回 **绝对 URL**（依据请求 scheme/host 推导，正确处理反代 root_path）。
- 复用现有纯逻辑层（`parsing` / `spec` / `rendering`），不改其行为；保持 `app/main.py` 薄。

## 端点

`POST /api/charts`，独立于浏览器表单端点 `POST /charts`，职责分离、互不干扰。

### 请求（`multipart/form-data`）

| 字段 | 类型 | 必填 | 省略时默认 |
|---|---|---|---|
| `file` | 文件 | 是 | — |
| `title` | 文本 | 否 | 上传文件名（去扩展名）；无文件名则 `"chart"` |
| `x_title` | 文本 | 否 | CSV 首列列名（`parsed.x_label`） |
| `x_eng` | 布尔 | 否 | `false` |
| `x_log` | 布尔 | 否 | `false` |
| `layout` | JSON 字符串 | 否 | 单面板：所有 Y 列指派到面板 0；`y_title` 取首个 Y 列名；`y_eng`/`y_log` = `false` |

- 传了 `layout` 就照现有表单逻辑走（`_build_spec` + `validate_spec`）。
- 不传 `layout` 则按上表的单面板默认构造 `ChartSpec`，实现「只传文件就能出图」。需要多面板时再给 `layout`。

`layout` 的结构与表单一致：

```json
{
  "panels": [{"y_title": "...", "y_eng": false, "y_log": false}],
  "assign": {"列名A": 0, "列名B": 1, "列名C": null}
}
```

`assign` 把每个 CSV 的 Y 列名映射到面板下标（`null` = 隐藏）；`validate_spec` 要求 `assign` 的键精确等于 CSV 的 Y 列名集合，且每个面板至少分配一条曲线。

### 成功响应 `201 Created`（`application/json`）

```json
{
  "id": "abc123",
  "page_url": "http://host:8000/chart/abc123",
  "png_url":  "http://host:8000/chart/abc123.png",
  "svg_url":  "http://host:8000/chart/abc123.svg",
  "csv_url":  "http://host:8000/chart/abc123.csv",
  "created_at": "2026-06-23T08:00:00+00:00"
}
```

- 四个资源 URL 用 `request.url_for("chart_page" / "chart_png" / "chart_svg" / "chart_csv", chart_id=...)` 生成绝对地址。
- `created_at` 为 UTC ISO 原文，供程序消费（非网页展示，调用方按需自行转换时区）。

### 错误响应

| 情况 | 状态码 | body |
|---|---|---|
| CSV 解析失败 / `layout` 无法解析 / 校验失败（面板、对数轴含 ≤0 等） | `400` | `{"detail": "<CSVParseError 文案>"}` |
| 缺 `file` / 字段类型错误 | `422` | FastAPI 默认校验响应（自带 JSON 结构） |

错误信息复用现有 `CSVParseError` 的中文文案；`detail` 键与 FastAPI `HTTPException` 默认一致。

## 架构落地

依赖方向不变（路由 → 逻辑/数据；纯逻辑层不反向依赖 Web）。

1. **纯逻辑（`app/spec.py`）**：新增纯函数 `default_spec(parsed: ParsedCSV, title: str, x_title: str) -> ChartSpec`，构造单面板默认配置。可脱离 Web 单测。
2. **薄路由（`app/main.py`）**：
   - 抽共享 helper `_create_chart(store, raw, spec) -> Chart`，封装「生成唯一 id + `store.save_chart`」。表单路由 `create_chart` 与新 API 路由都先各自构造 `ChartSpec`，再调此 helper，消除重复、保持薄。
   - 新增 `create_chart_api` 路由：读文件 → 构造 spec（有 `layout` 走 `_build_spec`，否则走 `default_spec`）→ `validate_spec` → `_create_chart` → 返回 JSON（含 4 个绝对 URL）。`CSVParseError` 捕获后转 `HTTPException(400)`。

## 测试（TDD）

- **纯逻辑**：`default_spec` 单测——单面板、所有 Y 列指派到面板 0、`y_title`/`x_title` 默认取列名、开关默认 false。
- **路由（FastAPI `TestClient` 端到端）**：
  - 仅传 `file` → `201` + 含 `id` 与四个绝对 URL（`page/png/svg/csv`）的 JSON；URL 可再次 GET 命中。
  - 传完整 `layout`（多面板）→ `201`，spec 正确落库。
  - CSV 解析错误 / 校验失败 → `400` + `{"detail": ...}`。
  - 缺 `file` → `422`。
  - 回归：抽出共享 helper 后，表单路由 `POST /charts` 仍 303 跳转、行为不变。

## 不做（YAGNI）

- 鉴权 / API Key、限流、JSON（内联 CSV 文本）请求体、相对路径 URL、幂等去重——均不在本次范围。
