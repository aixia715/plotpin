import json
import os

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.ids import new_id
from app.parsing import CSVParseError, read_csv_bytes
from app.rendering import build_plotly_spec, render_static
from app.spec import (
    ChartSpec,
    PanelSpec,
    auto_titles,
    default_spec,
    fill_empty_panel_y_titles,
    validate_spec,
)
from app.storage import Chart, Storage

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


def _build_spec(
    title: str,
    x_title: str,
    x_eng: bool,
    x_log: bool,
    layout_json: str,
    y_labels: list[str],
) -> ChartSpec:
    try:
        d = json.loads(layout_json)
        panels = [
            PanelSpec(p["y_title"], bool(p.get("y_eng")), bool(p.get("y_log")))
            for p in d["panels"]
        ]
        assign = {k: (None if v is None else int(v)) for k, v in d["assign"].items()}
    except (ValueError, KeyError, TypeError):
        raise CSVParseError("面板配置无法解析")
    spec = ChartSpec(title, x_title, bool(x_eng), bool(x_log), panels, assign)
    # Y 轴标题留空时自动用分配到该面板的首条曲线表头填充（逻辑见 app.spec）
    fill_empty_panel_y_titles(spec, y_labels)
    return spec


def _create_chart(store: Storage, raw: bytes, spec: ChartSpec) -> Chart:
    chart_id = new_id()
    while store.exists(chart_id):
        chart_id = new_id()
    return store.save_chart(chart_id, spec, raw)


@app.post("/charts")
async def create_chart(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    x_title: str | None = Form(None),
    x_eng: bool = Form(False),
    x_log: bool = Form(False),
    layout: str = Form(...),
    store: Storage = Depends(get_storage),
):
    raw = await file.read()
    try:
        parsed = read_csv_bytes(raw)
        auto_title, auto_x = auto_titles(file.filename, parsed)
        resolved_title = title or auto_title
        resolved_x_title = x_title or auto_x
        spec = _build_spec(
            resolved_title, resolved_x_title, x_eng, x_log, layout, parsed.y_labels
        )
        validate_spec(spec, parsed)
    except CSVParseError as err:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"items": _index_items(store), "error": str(err)},
            status_code=400,
        )
    chart = _create_chart(store, raw, spec)
    return RedirectResponse(url=f"/chart/{chart.id}", status_code=303)


@app.post("/api/charts")
async def create_chart_api(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    x_title: str | None = Form(None),
    x_eng: bool = Form(False),
    x_log: bool = Form(False),
    layout: str | None = Form(None),
    store: Storage = Depends(get_storage),
):
    raw = await file.read()
    try:
        parsed = read_csv_bytes(raw)
        auto_title, auto_x = auto_titles(file.filename, parsed)
        resolved_title = title or auto_title
        resolved_x_title = x_title or auto_x
        if layout is not None:
            spec = _build_spec(
                resolved_title, resolved_x_title, x_eng, x_log, layout, parsed.y_labels
            )
        else:
            spec = default_spec(parsed, resolved_title, resolved_x_title, x_eng, x_log)
        validate_spec(spec, parsed)
    except CSVParseError as err:
        raise HTTPException(status_code=400, detail=str(err))
    chart = _create_chart(store, raw, spec)
    return JSONResponse(
        status_code=201,
        content={
            "id": chart.id,
            "page_url": str(request.url_for("chart_page", chart_id=chart.id)),
            "png_url": str(request.url_for("chart_png", chart_id=chart.id)),
            "svg_url": str(request.url_for("chart_svg", chart_id=chart.id)),
            "csv_url": str(request.url_for("chart_csv", chart_id=chart.id)),
            "created_at": chart.created_at,
        },
    )


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


@app.get("/chart/{chart_id}.csv")
def chart_csv(chart_id: str, store: Storage = Depends(get_storage)):
    if store.get_chart(chart_id) is None:
        return _not_found_plain()
    return Response(
        content=store.read_csv(chart_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{chart_id}.csv"'},
    )


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
        # 传 dict,由模板 `| tojson` 做 script 上下文安全转义(转义 <>& 防 </script> 破坏块)
        {"chart": chart, "spec": spec, "log_warning": spec["warning"]},
    )


def _not_found_plain() -> Response:
    return Response(content="404", media_type="text/plain", status_code=404)
