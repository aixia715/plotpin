import pytest
from fastapi.testclient import TestClient

from app.main import app, get_storage
from app.storage import Storage


@pytest.fixture()
def client(tmp_path):
    store = Storage(tmp_path)
    app.dependency_overrides[get_storage] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _upload(client, csv_text):
    return client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "y_title": "Y",
              "x_eng": "on", "y_eng": "on"},
        files={"file": ("data.csv", csv_text.encode("utf-8"), "text/csv")},
        follow_redirects=False,
    )


def test_index_empty(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_upload_success_redirects(client):
    resp = _upload(client, "x,y\n1k,3.3\n2k,6.6\n")
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/chart/")


def test_upload_bad_cell_shows_error(client):
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "y_title": "Y"},
        files={"file": ("data.csv", b"x,y\n1k,47x\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "47x" in resp.text


def test_chart_page_and_listing(client):
    loc = _upload(client, "x,y\n1k,3.3\n2k,6.6\n").headers["location"]
    chart_id = loc.rsplit("/", 1)[-1]
    page = client.get(f"/chart/{chart_id}")
    assert page.status_code == 200
    assert chart_id in client.get("/").text


def test_chart_not_found(client):
    assert client.get("/chart/missing").status_code == 404


def test_chart_page_has_http_copy_fallback(client):
    chart_id = _upload(client, "x,y\n1k,3.3\n2k,6.6\n").headers["location"].rsplit("/", 1)[-1]
    page = client.get(f"/chart/{chart_id}")
    # 局域网纯 HTTP 需要 execCommand 兜底,不能只用 Clipboard API
    assert "execCommand" in page.text


def test_png_render_and_cache(client, tmp_path):
    chart_id = _upload(client, "x,y\n1k,3.3\n2k,6.6\n").headers["location"].rsplit("/", 1)[-1]
    resp = client.get(f"/chart/{chart_id}.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
    # 第二次请求应命中缓存文件
    cached = tmp_path / "cache" / f"{chart_id}.png"
    assert cached.exists()


def test_upload_log_with_nonpositive_rejected(client):
    # X 轴设为对数,但数据含 0 → 应 400 报错
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "y_title": "Y", "x_log": "on"},
        files={"file": ("data.csv", b"x,y\n0,3.3\n1k,6.6\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert "对数" in resp.text


def test_upload_log_positive_ok(client):
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "y_title": "Y", "x_log": "on", "y_log": "on"},
        files={"file": ("data.csv", b"x,y\n1k,3.3\n10k,6.6\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_svg_render(client):
    chart_id = _upload(client, "x,y\n1k,3.3\n2k,6.6\n").headers["location"].rsplit("/", 1)[-1]
    resp = client.get(f"/chart/{chart_id}.svg")
    assert resp.status_code == 200
    assert "image/svg" in resp.headers["content-type"]


def test_index_thumbnail_only_when_cached(client):
    chart_id = _upload(client, "x,y\n1k,3.3\n2k,6.6\n").headers["location"].rsplit("/", 1)[-1]
    # 未访问 PNG 前:首页不应出现该图的缩略图 img(占位)
    assert f'src="/chart/{chart_id}.png"' not in client.get("/").text
    # 访问一次 PNG 触发缓存后:首页应出现缩略图 img
    client.get(f"/chart/{chart_id}.png")
    assert f'src="/chart/{chart_id}.png"' in client.get("/").text
