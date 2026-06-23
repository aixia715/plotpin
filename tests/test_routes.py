import json

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


def _layout(panels, assign):
    return json.dumps({"panels": panels, "assign": assign})


def _upload(client, csv_text, layout=None):
    if layout is None:
        layout = _layout(
            [{"y_title": "Y", "y_eng": True, "y_log": False}],
            {"y": 0},
        )
    return client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "x_eng": "on", "layout": layout},
        files={"file": ("data.csv", csv_text.encode("utf-8"), "text/csv")},
        follow_redirects=False,
    )


def test_index_empty(client):
    assert client.get("/").status_code == 200


def test_upload_success_redirects(client):
    resp = _upload(client, "x,y\n1000,3.3\n2000,6.6\n")
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/chart/")


def test_upload_two_panels(client):
    layout = _layout(
        [{"y_title": "上", "y_eng": True, "y_log": False},
         {"y_title": "下", "y_eng": True, "y_log": False}],
        {"a": 0, "b": 1},
    )
    resp = _upload(client, "x,a,b\n1000,3.3,0.1\n2000,6.6,0.2\n", layout)
    assert resp.status_code == 303


def test_upload_bad_cell_shows_error(client):
    resp = _upload(client, "x,y\n1000,47x\n")
    assert resp.status_code == 400
    assert "47x" in resp.text


def test_upload_all_hidden_rejected(client):
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": False}], {"y": None})
    resp = _upload(client, "x,y\n1000,3.3\n2000,6.6\n", layout)
    assert resp.status_code == 400


def test_upload_bad_layout_json(client):
    resp = _upload(client, "x,y\n1000,3.3\n", layout="{not json")
    assert resp.status_code == 400


def test_chart_page_and_listing(client):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    assert client.get(f"/chart/{chart_id}").status_code == 200
    assert chart_id in client.get("/").text


def test_chart_page_escapes_script_in_title(client):
    # 标题含 </script> 不得破坏 spec script 块(script 上下文 XSS / 永久链接损坏)
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": False}], {"y": 0})
    chart_id = client.post(
        "/charts",
        data={
            "title": "</script><script>alert(1)</script>",
            "x_title": "X", "x_eng": "on", "layout": layout,
        },
        files={"file": ("d.csv", b"x,y\n1000,3.3\n2000,6.6\n", "text/csv")},
        follow_redirects=False,
    ).headers["location"].rsplit("/", 1)[-1]
    page = client.get(f"/chart/{chart_id}").text
    # 取 spec 块内容:从 id="spec" 后的 > 到第一个 </script>
    start = page.index('id="spec"')
    content_start = page.index(">", start) + 1
    content = page[content_start:page.index("</script>", content_start)]
    # 注入的 </script> 必须被转义,spec 块仍是完整可解析 JSON,标题原样还原
    assert json.loads(content)["layout"]["title"]["text"] == "</script><script>alert(1)</script>"


def test_chart_not_found(client):
    assert client.get("/chart/missing").status_code == 404


def test_chart_page_has_http_copy_fallback(client):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    assert "execCommand" in client.get(f"/chart/{chart_id}").text


def test_png_render_and_cache(client, tmp_path):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    resp = client.get(f"/chart/{chart_id}.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert (tmp_path / "cache" / f"{chart_id}.png").exists()


def test_upload_log_partial_nonpositive_now_succeeds(client):
    # X 对数 + 含 0：自动剔除 0 行，应 303 成功(不再 400)
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": False}], {"y": 0})
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "x_log": "on", "layout": layout},
        files={"file": ("data.csv", b"x,y\n0,3.3\n1000,6.6\n10000,9.9\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_chart_page_shows_log_warning(client):
    # Y 对数面板 + 含 0：图表页应出现警告文案
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": True}], {"y": 0})
    loc = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "x_eng": "on", "layout": layout},
        files={"file": ("data.csv", b"x,y\n1000,0\n2000,6.6\n3000,9.9\n", "text/csv")},
        follow_redirects=False,
    ).headers["location"]
    chart_id = loc.rsplit("/", 1)[-1]
    page = client.get(f"/chart/{chart_id}")
    assert "对数 Y 轴包含 ≤0 的值，已自动忽略" in page.text


def test_upload_log_all_nonpositive_still_rejected(client):
    # X 对数但所有 x≤0：无正数可画，仍应 400
    layout = _layout([{"y_title": "Y", "y_eng": True, "y_log": False}], {"y": 0})
    resp = client.post(
        "/charts",
        data={"title": "T", "x_title": "X", "x_log": "on", "layout": layout},
        files={"file": ("data.csv", b"x,y\n0,3.3\n-1,6.6\n", "text/csv")},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_svg_render(client):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    resp = client.get(f"/chart/{chart_id}.svg")
    assert resp.status_code == 200
    assert "image/svg" in resp.headers["content-type"]


def test_csv_download(client):
    csv_text = "x,y\n1000,3.3\n2000,6.6\n"
    chart_id = _upload(client, csv_text).headers["location"].rsplit("/", 1)[-1]
    resp = client.get(f"/chart/{chart_id}.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert f"{chart_id}.csv" in resp.headers["content-disposition"]
    assert resp.content == csv_text.encode("utf-8")


def test_csv_download_not_found(client):
    assert client.get("/chart/missing.csv").status_code == 404


def test_index_thumbnail_only_when_cached(client):
    chart_id = _upload(client, "x,y\n1000,3.3\n2000,6.6\n").headers["location"].rsplit("/", 1)[-1]
    assert f'src="/chart/{chart_id}.png"' not in client.get("/").text
    client.get(f"/chart/{chart_id}.png")
    assert f'src="/chart/{chart_id}.png"' in client.get("/").text
