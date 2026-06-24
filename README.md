# PlotPin

局域网自部署的图表分享应用：上传 CSV 生成 Plotly 图表，并提供**永久不变**的页面 / PNG / SVG 链接，可拷贝插入笔记中长期引用。

单人使用、无需登录、部署在 NAS（或任意局域网主机）上，CSV 与元数据通过 Docker volume 持久化，容器重建 / 升级后链接依旧有效。

## 功能

- 上传 CSV → 配置坐标轴与标题 → 生成折线图
- 第一列为 X，其余列为 Y（可多列同图，表头作图例）
- X / Y 轴可选**工程计数法**（如 `47000 → 47k`、`0.1 → 100m`）与**对数坐标**
- 每张图分配唯一不可猜测的短 ID，提供三种永久地址：
  - 交互页：`/chart/<id>` —— Plotly 悬停看数值、缩放
  - 静态图：`/chart/<id>.png`、`/chart/<id>.svg` —— 可用 `![](url)` 嵌入笔记
- 网页上所有时间按**访问者浏览器本地时间**显示（后端存 UTC，前端转换）

## 技术栈

- 后端：FastAPI + Uvicorn
- 模板：Jinja2（`templates/`）
- 前端：原生 JavaScript（`static/`）+ Plotly.js
- CSV 解析：pandas
- 静态出图：matplotlib（Agg 无头模式，PNG / SVG）
- 存储：SQLite + 文件系统（`app/storage.py`）
- 打包：Docker / docker-compose

## 快速开始（Docker）

```bash
docker compose up -d --build
```

默认监听 `http://localhost:8000`，数据持久化在 `./data` 卷。把 `docker-compose.yml` 中左侧路径改成 NAS 上的实际共享目录即可长期保存。

健康检查：`curl http://localhost:8000/healthz` → `{"status":"ok"}`。

## 本地开发

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

默认数据目录为 `./data`，可通过环境变量 `PLOTPIN_DATA_DIR` 覆盖。

## 测试

```bash
pytest -q
```

纯逻辑层（`eng_notation` / `parsing` / `rendering` / `ids`）可脱离 Web 与数据库直接单测，是测试投入重点。

## CSV 格式约定

- **含表头行**，表头作为每条曲线的名称（图例）
- **第一列 = X**，**第二列及以后 = Y**（可多列）
- 数值支持小数与科学计数法（如 `1.5e6`），不支持 SI 词头（工程计数法仅用于显示）
- 编码优先 UTF-8，自动兜底 GBK
- 启用对数坐标时对应轴的所有值必须 > 0

示例：

```csv
频率,增益,相位
100,1.0,-0.1
1000,10.0,-0.9
10000,42.0,-3.2
```

## 项目结构

```
app/
  eng_notation.py   # 坐标轴工程计数法显示与刻度计算（纯逻辑）
  parsing.py        # CSV 解析、数值校验、解析报告（纯逻辑）
  rendering.py      # 构建 Plotly spec、matplotlib 静态出图（纯逻辑）
  ids.py            # 稳定分享 id 生成（纯逻辑）
  storage.py        # SQLite 读写、建表（数据访问）
  main.py           # FastAPI 装配与薄路由
templates/          # Jinja2 模板
static/             # 原生 JS / Plotly.js / 样式
tests/              # pytest 单测
Dockerfile / docker-compose.yml
```

## 架构

三层：**纯逻辑**（零 Web/DB 依赖，测试重点）→ **数据访问层** → **薄路由**（收请求 → 调逻辑 → 渲染模板）。依赖只能从外往里指（路由 → 数据 / 逻辑，逻辑层内部 `rendering → parsing → eng_notation`），不得反向依赖。新业务逻辑优先放纯逻辑层并配单测，保持 `app/main.py` 薄。详见 `CLAUDE.md`。

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `PLOTPIN_DATA_DIR` | `data` | 数据目录（SQLite 数据库、CSV、图片缓存） |

## 路由

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET`  | `/` | 首页：上传 + 记录列表 |
| `POST` | `/charts` | 上传 CSV 并生成图表（重定向到图表页） |
| `GET`  | `/chart/<id>` | 交互式图表页 |
| `GET`  | `/chart/<id>.png` | 静态 PNG（首次访问时渲染并缓存） |
| `GET`  | `/chart/<id>.svg` | 静态 SVG（首次访问时渲染并缓存） |
| `POST` | `/api/charts` | 编程式提交 CSV 生成图表，返回 JSON（见下） |
| `GET`  | `/healthz` | 健康检查 |

供其他应用编程调用的 `POST /api/charts`（multipart 上传 CSV，返回页面 / PNG / SVG / CSV 的绝对 URL）详见 [docs/API.md](docs/API.md)。

## 许可

本项目为个人自部署工具，暂未声明开源许可证。
