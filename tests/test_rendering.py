from app.parsing import ParsedCSV
from app.rendering import render_static, build_plotly_spec


def _sample() -> ParsedCSV:
    return ParsedCSV(
        x_label="freq",
        x=[1000.0, 2000.0, 3000.0],
        y_labels=["gain", "phase"],
        ys=[[3.3, 6.6, 9.9], [0.1, 0.2, 0.3]],
    )


def test_render_png_returns_png_bytes():
    data = render_static(_sample(), "T", "X", "Y", True, True, False, False, "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_svg_returns_svg():
    data = render_static(_sample(), "T", "X", "Y", True, True, False, False, "svg")
    assert b"<svg" in data[:512]


def test_render_log_axis_png():
    # 对数轴(数据全为正)应正常出图
    data = render_static(_sample(), "T", "X", "Y", True, True, True, True, "png")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_build_plotly_spec_structure():
    spec = build_plotly_spec(_sample(), "T", "X", "Y", True, False, False, False)
    assert len(spec["data"]) == 2
    assert spec["data"][0]["name"] == "gain"
    assert spec["data"][0]["x"] == [1000.0, 2000.0, 3000.0]
    assert spec["layout"]["title"]["text"] == "T"
    # 线性轴不应带 type=log
    assert spec["layout"]["xaxis"].get("type") != "log"
    # x 轴工程计数法显示:刻度文本含 SI 词头
    assert any("k" in t for t in spec["layout"]["xaxis"]["ticktext"])
    # y 轴关闭工程计数法:刻度文本为普通数字(无字母后缀)
    assert all(not any(ch.isalpha() for ch in t)
               for t in spec["layout"]["yaxis"]["ticktext"])


def test_build_plotly_spec_log_axis():
    spec = build_plotly_spec(_sample(), "T", "X", "Y", True, True, True, False)
    assert spec["layout"]["xaxis"]["type"] == "log"
    assert spec["layout"]["yaxis"].get("type") != "log"
    # 对数轴刻度应为 10 的整数幂
    assert all(abs(round(__import__("math").log10(t)) - __import__("math").log10(t)) < 1e-9
               for t in spec["layout"]["xaxis"]["tickvals"])
