import json
import os

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.ids import new_id
from app.parsing import CSVParseError, check_log_positivity, read_csv_bytes
from app.rendering import build_plotly_spec, render_static
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
            # 仅当 PNG 缓存已存在时给缩略图 URL,否则 None(首页不触发渲染)
            "thumb": f"/chart/{c.id}.png" if store.cache_path(c.id, "png").exists() else None,
        }
        for c in store.list_charts()
    ]


@app.get("/", response_class=HTMLResponse)
def index(request: Request, store: Storage = Depends(get_storage)):
    return templates.TemplateResponse(request, "index.html", {"items": _index_items(store)})


@app.post("/charts")
async def create_chart(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    x_title: str = Form(...),
    y_title: str = Form(...),
    x_eng: bool = Form(False),
    y_eng: bool = Form(False),
    x_log: bool = Form(False),
    y_log: bool = Form(False),
    store: Storage = Depends(get_storage),
):
    raw = await file.read()
    try:
        parsed = read_csv_bytes(raw)             # 解析 + 逐格校验
        check_log_positivity(parsed, x_log, y_log)  # 对数 + ≤0 冲突校验
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
    store.save_chart(chart_id, title, x_title, y_title, x_eng, y_eng, x_log, y_log, raw)
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
    data = render_static(
        parsed, chart.title, chart.x_title, chart.y_title,
        chart.x_eng, chart.y_eng, chart.x_log, chart.y_log, ext,
    )
    cache.write_bytes(data)
    return Response(content=data, media_type=media_type)


@app.get("/chart/{chart_id}", response_class=HTMLResponse)
def chart_page(chart_id: str, request: Request, store: Storage = Depends(get_storage)):
    chart = store.get_chart(chart_id)
    if chart is None:
        return templates.TemplateResponse(request, "404.html", {}, status_code=404)
    parsed = read_csv_bytes(store.read_csv(chart_id))
    spec = build_plotly_spec(
        parsed, chart.title, chart.x_title, chart.y_title,
        chart.x_eng, chart.y_eng, chart.x_log, chart.y_log,
    )
    return templates.TemplateResponse(
        request,
        "chart.html",
        {"chart": chart, "spec_json": json.dumps(spec)},
    )


def _not_found_plain() -> Response:
    return Response(content="404", media_type="text/plain", status_code=404)
