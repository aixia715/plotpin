# PlotPin HTTP API

供其他应用以编程方式提交 CSV + 绘图配置，拿回图表的分享页 / PNG / SVG / CSV 的**绝对 URL**。

- 局域网自部署，**不鉴权**（与浏览器上传一致，假定局域网可信）。
- CSV 以 **multipart 文件上传** 传入，`curl -F` 即可调用。
- 返回的资源 URL 为**绝对地址**（依据请求 scheme/host 推导，正确处理反向代理的 root_path）。
- 端点 `POST /api/charts` 独立于浏览器表单端点 `POST /charts`，互不干扰。

下文示例假定服务运行在 `http://localhost:8000`，请按实际部署地址替换。

---

## `POST /api/charts`

上传 CSV 并生成图表。

### 请求

`Content-Type: multipart/form-data`

| 字段 | 类型 | 必填 | 省略时默认 |
|---|---|---|---|
| `file` | 文件 | 是 | — |
| `title` | 文本 | 否 | 上传文件名（去扩展名）；无文件名则 `"chart"` |
| `x_title` | 文本 | 否 | CSV 首列列名 |
| `x_eng` | 布尔 | 否 | `false`（X 轴工程计数法，如 `47000 → 47k`） |
| `x_log` | 布尔 | 否 | `false`（X 轴对数坐标） |
| `layout` | JSON 字符串 | 否 | 单面板：所有 Y 列指派到面板 0；`y_title` 取首个 Y 列名；`y_eng` / `y_log` = `false` |

**CSV 格式约定**（与上传页一致）：含表头行（表头作图例名）、第一列为 X、其余列为 Y；数值支持小数与科学计数法（如 `1.5e6`），编码优先 UTF-8、自动兜底 GBK。

**布尔字段**：传 `true` / `false`（multipart 表单文本即可）。

#### `layout`（可选，多面板）

不传 `layout` 时按上表默认构造**单面板**配置，实现「只传文件就能出图」；需要多面板时再给 `layout`：

```json
{
  "panels": [
    {"y_title": "增益(dB)", "y_eng": false, "y_log": false},
    {"y_title": "相位(°)",  "y_eng": false, "y_log": false}
  ],
  "assign": {"增益": 0, "相位": 1, "备注列": null}
}
```

- `panels`：面板数组，每个面板含 `y_title`、`y_eng`、`y_log`。
- `assign`：把每个 CSV 的 **Y 列名**映射到面板下标（从 0 开始），`null` 表示隐藏该列。
- 约束（由 `validate_spec` 校验）：`assign` 的键必须**精确等于** CSV 的 Y 列名集合，每个面板至少分配一条曲线，至少显示一条曲线。
- 启用对数轴时，对应轴若**全部** ≤0 会被拒绝；部分 ≤0 仅被剔除、不报错。

### 成功响应 `201 Created`

`Content-Type: application/json`

```json
{
  "id": "abc123",
  "page_url": "http://localhost:8000/chart/abc123",
  "png_url":  "http://localhost:8000/chart/abc123.png",
  "svg_url":  "http://localhost:8000/chart/abc123.svg",
  "csv_url":  "http://localhost:8000/chart/abc123.csv",
  "created_at": "2026-06-23T08:00:00+00:00"
}
```

- 四个 URL 为永久不变的绝对地址：交互页、静态 PNG、静态 SVG、原始 CSV。可直接用 `![](png_url)` 嵌入笔记。
- `created_at` 为 **UTC ISO 原文**，供程序消费；如需展示给人，调用方自行转换为本地时区。

### 错误响应

| 情况 | 状态码 | body |
|---|---|---|
| CSV 解析失败 / `layout` 无法解析 / 校验失败（面板、对数轴全 ≤0 等） | `400` | `{"detail": "<错误文案>"}` |
| 缺 `file` / 字段类型错误 | `422` | FastAPI 默认校验响应（JSON 结构） |

错误文案复用内部 `CSVParseError` 的中文提示。

---

## 示例

### 最简：只传文件

```bash
curl -F file=@data.csv http://localhost:8000/api/charts
```

### 带标题与 X 轴选项

```bash
curl -F file=@bode.csv \
     -F title="波特图" \
     -F x_title="频率(Hz)" \
     -F x_log=true \
     http://localhost:8000/api/charts
```

### 多面板（layout）

```bash
curl -F file=@bode.csv \
     -F title="波特图" \
     -F x_title="频率(Hz)" \
     -F x_log=true \
     -F 'layout={"panels":[{"y_title":"增益(dB)","y_eng":false,"y_log":false},{"y_title":"相位(°)","y_eng":false,"y_log":false}],"assign":{"增益":0,"相位":1}}' \
     http://localhost:8000/api/charts
```

### Python（requests）

```python
import requests

with open("data.csv", "rb") as f:
    r = requests.post(
        "http://localhost:8000/api/charts",
        files={"file": ("data.csv", f, "text/csv")},
        data={"title": "测量结果", "x_title": "频率(Hz)", "x_log": "true"},
    )
r.raise_for_status()
urls = r.json()
print(urls["page_url"], urls["png_url"])
```

---

## 健康检查

```bash
curl http://localhost:8000/healthz   # -> {"status":"ok"}
```
