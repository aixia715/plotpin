import math

from app.parsing import ParsedCSV
from app.rendering import build_plotly_spec, render_static
from app.spec import ChartSpec, PanelSpec


def _sample() -> ParsedCSV:
    return ParsedCSV(
        x_label="freq",
        x=[1000.0, 2000.0, 3000.0],
        y_labels=["gain", "phase"],
        ys=[[3.3, 6.6, 9.9], [0.1, 0.2, 0.3]],
    )


def _one_panel(x_eng=True, y_eng=False, x_log=False, y_log=False) -> ChartSpec:
    # 单面板：gain、phase 都在面板 0
    return ChartSpec("T", "X", x_eng, x_log,
                     [PanelSpec("Y", y_eng, y_log)],
                     {"gain": 0, "phase": 0})


def test_build_plotly_spec_structure():
    spec = build_plotly_spec(_sample(), _one_panel(x_eng=True, y_eng=False))
    assert len(spec["data"]) == 2
    assert spec["data"][0]["name"] == "gain"
    assert spec["data"][0]["x"] == [1000.0, 2000.0, 3000.0]
    assert spec["layout"]["title"]["text"] == "T"
    assert spec["layout"]["xaxis"].get("type") != "log"
    assert any("k" in t for t in spec["layout"]["xaxis"]["ticktext"])
    assert all(not any(ch.isalpha() for ch in t)
               for t in spec["layout"]["yaxis"]["ticktext"])


def test_build_plotly_spec_log_axis():
    spec = build_plotly_spec(_sample(), _one_panel(x_eng=True, y_eng=True, x_log=True, y_log=False))
    assert spec["layout"]["xaxis"]["type"] == "log"
    assert spec["layout"]["yaxis"].get("type") != "log"
    assert all(abs(round(math.log10(t)) - math.log10(t)) < 1e-9
               for t in spec["layout"]["xaxis"]["tickvals"])


def test_build_plotly_spec_two_panels():
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("上", True, False), PanelSpec("下", True, True)],
                     {"gain": 0, "phase": 1})
    out = build_plotly_spec(_sample(), spec)
    by_name = {t["name"]: t for t in out["data"]}
    assert by_name["gain"]["yaxis"] == "y"
    assert by_name["phase"]["yaxis"] == "y2"
    assert out["layout"]["yaxis"]["title"]["text"] == "上"
    assert out["layout"]["yaxis2"]["title"]["text"] == "下"
    # 面板 1 为对数
    assert out["layout"]["yaxis"].get("type") != "log"
    assert out["layout"]["yaxis2"]["type"] == "log"


def test_build_plotly_spec_hidden_curve_excluded():
    spec = ChartSpec("T", "X", True, False, [PanelSpec("Y", True, False)],
                     {"gain": 0, "phase": None})
    out = build_plotly_spec(_sample(), spec)
    assert [t["name"] for t in out["data"]] == ["gain"]


def test_render_png_returns_png_bytes():
    data = render_static(_sample(), _one_panel(x_eng=True, y_eng=True), "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_svg_returns_svg():
    data = render_static(_sample(), _one_panel(x_eng=True, y_eng=True), "svg")
    assert b"<svg" in data[:512]


def test_render_two_panels_png():
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("上", True, False), PanelSpec("下", True, True)],
                     {"gain": 0, "phase": 1})
    data = render_static(_sample(), spec, "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_log_axis_png():
    spec = _one_panel(x_eng=True, y_eng=True, x_log=True, y_log=True)
    data = render_static(_sample(), spec, "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
