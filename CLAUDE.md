# PlotPin

局域网自部署的图表分享应用：上传 CSV 生成 Plotly 图表，提供永久不变的页面 / PNG / SVG 链接。

## 技术栈
- 后端：FastAPI + Uvicorn
- 模板：Jinja2（`templates/`）
- 前端：原生 JavaScript（`static/`）+ Plotly.js
- 存储：SQLite（`app/storage.py`）

## 规则

### 时间显示
网页上展示给用户的所有时间，必须显示为访问者**浏览器的本地时间**。

- 后端一律以 UTC 存储和传输时间（`datetime.now(timezone.utc).isoformat()`）。
- 时区转换只在前端进行：用
  `<time class="local-time" datetime="{UTC ISO}">{UTC ISO}</time>` 承载时间，
  由 `static/localtime.js` 在页面加载后转成浏览器本地时间。
- 元素文本初始为原始 ISO 字符串，保证无 JS 时优雅降级为 UTC 原文。
- 新增任何时间展示都必须沿用此模式，禁止直接把 UTC 原始字符串渲染给用户。
