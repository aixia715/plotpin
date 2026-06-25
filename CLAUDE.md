# PlotPin

局域网自部署的图表分享应用：上传 CSV 生成 Plotly 图表，提供稳定不变的页面 / PNG / SVG 链接（记录删除前链接始终有效）。

## 技术栈
- 后端：FastAPI + Uvicorn
- 模板：Jinja2（`templates/`）
- 前端：原生 JavaScript（`static/`）+ Plotly.js
- 存储：SQLite（`app/storage.py`）

## 架构

三层：纯逻辑（零 Web/DB 依赖，测试重点）→ 数据访问层 → 薄路由（收请求 → 调逻辑 → 渲染模板）。依赖只能从外往里指（路由 → 数据 / 逻辑，逻辑层内部 `rendering → spec → parsing → eng_notation`），不得反向依赖。

| 层 | 文件 | 职责 |
|---|---|---|
| 纯逻辑 | `app/eng_notation.py` | 坐标轴工程计数法显示与刻度计算 |
| 纯逻辑 | `app/parsing.py` | CSV 解析、数值校验、解析报告 |
| 纯逻辑 | `app/spec.py` | ChartSpec/PanelSpec 多面板配置、序列化与 validate_spec 校验（依赖 parsing） |
| 纯逻辑 | `app/rendering.py` | 吃 ChartSpec 构建多面板 Plotly spec、matplotlib 静态出图（PNG/SVG） |
| 纯逻辑 | `app/ids.py` | 稳定分享 id 生成 |
| 数据访问 | `app/storage.py` | SQLite 读写、建表 |
| 薄路由 | `app/main.py` | FastAPI 装配与路由：收请求 → 调逻辑 → 渲染模板/返回图片 |
| 视图 | `templates/`、`static/` | Jinja2 模板 + 原生 JS / Plotly.js |

新业务逻辑优先放纯逻辑层并配单测，保持 `app/main.py` 薄——不要把业务逻辑塞进路由。

## 规则

### 任务开始前同步 master
每次新开任务前，先确认本地 `master` 分支与远程仓库最新一致：`git fetch` 后检查 `git status` / `git log origin/master`，必要时 `git pull`（或基于最新 `origin/master` 新建分支）。避免基于过时代码开工导致后续合并冲突。

### 测试（TDD）
改动遵循 TDD：先写失败测试再实现。纯逻辑层（`eng_notation` / `parsing` / `spec` / `rendering` / `ids`）是测试投入重点，应能脱离 Web 与数据库直接单测。测试在 `tests/`，用 `pytest` 运行。

### 前端设计
改前端（`templates/`、`static/`）做视觉 / UI 设计时，若 `frontend-design` skill 可用（`claude-plugins-official` 插件）则启用并遵循其设计取向、排版与组件取舍指引；不可用时按其设计原则手工实现，不阻塞进度。

### 时间显示
网页上展示给用户的所有时间，必须显示为访问者**浏览器的本地时间**。

- 后端一律以 UTC 存储和传输时间（`datetime.now(timezone.utc).isoformat()`）。
- 时区转换只在前端进行：用
  `<time class="local-time" datetime="{UTC ISO}">{UTC ISO}</time>` 承载时间，
  由 `static/localtime.js` 在页面加载后转成浏览器本地时间。
- 元素文本初始为原始 ISO 字符串，保证无 JS 时优雅降级为 UTC 原文。
- 新增任何时间展示都必须沿用此模式，禁止直接把 UTC 原始字符串渲染给用户。
