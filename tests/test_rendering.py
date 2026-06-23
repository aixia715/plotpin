import io
import math

from app.parsing import ParsedCSV
from app.rendering import build_plotly_spec, render_static
from app.spec import ChartSpec, PanelSpec

# matplotlib 默认网格线灰 (#b0b0b0 = RGB 176,176,176)，用于断言静态图带网格
_GRID_GRAY_HEX = "#b0b0b0"
_GRID_GRAY_RGB = (176, 176, 176)


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
    # 面板 0 在上（domain 底边 ≥ 面板 1 顶边）
    assert out["layout"]["yaxis"]["domain"][0] >= out["layout"]["yaxis2"]["domain"][1]


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


def test_ticks_ignore_none():
    from app.rendering import _ticks
    ticks = _ticks([None, 1.0, 10.0, 100.0], True)
    assert ticks
    assert all(t > 0 for t in ticks)


def test_build_spec_y_log_nulls_nonpositive_and_warns():
    from app.rendering import build_plotly_spec
    parsed = ParsedCSV("x", [1.0, 10.0, 100.0], ["gain"], [[0.0, 5.0, 50.0]])
    spec = ChartSpec("T", "X", False, False, [PanelSpec("Y", False, True)], {"gain": 0})
    out = build_plotly_spec(parsed, spec)
    assert out["data"][0]["y"][0] is None
    assert out["data"][0]["y"][1:] == [5.0, 50.0]
    assert out["data"][0]["customdata"][0][1] is None   # None 点 customdata 不崩
    assert out["warning"] == "对数 Y 轴包含 ≤0 的值，已自动忽略"


def test_build_spec_x_log_drops_rows_and_warns():
    from app.rendering import build_plotly_spec
    parsed = ParsedCSV("x", [0.0, 10.0, 100.0], ["gain"], [[1.0, 2.0, 3.0]])
    spec = ChartSpec("T", "X", False, True, [PanelSpec("Y", False, False)], {"gain": 0})
    out = build_plotly_spec(parsed, spec)
    assert out["data"][0]["x"] == [10.0, 100.0]
    assert out["data"][0]["y"] == [2.0, 3.0]
    assert out["warning"] == "对数 X 轴包含 ≤0 的值，已自动忽略"


def test_build_spec_both_axes_warning_text():
    from app.rendering import build_plotly_spec
    # x=0.0 → x_log 行过滤(x_dropped); 剩余 x=[10.0, 100.0], gain=[-1.0, 50.0] → y_log 点置 None(y_dropped)
    parsed = ParsedCSV("x", [0.0, 10.0, 100.0], ["gain"], [[5.0, -1.0, 50.0]])
    spec = ChartSpec("T", "X", False, True, [PanelSpec("Y", False, True)], {"gain": 0})
    out = build_plotly_spec(parsed, spec)
    assert out["warning"] == "对数 X 轴和 Y 轴包含 ≤0 的值，已自动忽略"


def test_build_spec_no_warning_when_clean():
    from app.rendering import build_plotly_spec
    out = build_plotly_spec(_sample(), _one_panel(x_log=True, y_log=True))
    assert out["warning"] == ""


def test_render_static_with_gaps_does_not_crash():
    from app.rendering import render_static
    parsed = ParsedCSV("x", [1.0, 10.0, 100.0], ["gain"], [[0.0, 5.0, 50.0]])
    spec = ChartSpec("T", "X", False, False, [PanelSpec("Y", False, True)], {"gain": 0})
    data = render_static(parsed, spec, "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_svg_has_grid_lines():
    # PNG/SVG 静态图必须带网格；matplotlib 网格线默认用 #b0b0b0 灰
    data = render_static(_sample(), _one_panel(x_eng=True, y_eng=False), "svg")
    text = data.decode("utf-8", errors="replace")
    assert _GRID_GRAY_HEX in text


def test_render_png_has_grid_lines():
    # PNG 为二进制，用 PIL 解码后统计网格灰像素，确认网格确实画进位图
    import numpy as np
    from PIL import Image
    data = render_static(_sample(), _one_panel(x_eng=True, y_eng=False), "png")
    img = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
    gray = int(np.sum(np.all(img == _GRID_GRAY_RGB, axis=-1)))
    assert gray > 100  # 网格灰像素应明显存在（无网格时仅个位数抗锯齿噪点）


def test_render_svg_two_panels_both_have_grid():
    # 多面板时每个面板都应带网格
    spec = ChartSpec("T", "X", True, False,
                     [PanelSpec("上", True, False), PanelSpec("下", True, True)],
                     {"gain": 0, "phase": 1})
    data = render_static(_sample(), spec, "svg")
    text = data.decode("utf-8", errors="replace")
    # 两个面板各有 X/Y 方向网格，网格灰样式应出现多次
    assert text.count(_GRID_GRAY_HEX) >= 4
