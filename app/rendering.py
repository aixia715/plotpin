import io

import matplotlib

matplotlib.use("Agg")  # 无头环境,必须在 pyplot 之前设置

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from app.eng_notation import format_eng, format_plain, log_ticks, nice_ticks  # noqa: E402
from app.parsing import ParsedCSV  # noqa: E402

# 若系统装有中文字体(如 Docker 镜像里的 fonts-noto-cjk),则启用,
# 让静态 PNG/SVG 的中文标题/轴标签正常显示。本地未安装时保持默认,
# 不改 rcParams,避免 findfont 警告污染测试输出。
_CJK_CANDIDATES = (
    "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK TC",
    "Noto Sans CJK KR", "WenQuanYi Zen Hei", "Source Han Sans SC",
)
_available_fonts = {f.name for f in font_manager.fontManager.ttflist}
_cjk_font = next((name for name in _CJK_CANDIDATES if name in _available_fonts), None)
if _cjk_font:
    plt.rcParams["font.sans-serif"] = [_cjk_font, "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False  # 用 ASCII 减号,避免负号缺字形


def _formatter(use_eng: bool):
    return format_eng if use_eng else format_plain


def _ticks(values, use_log: bool):
    lo, hi = min(values), max(values)
    return log_ticks(lo, hi) if use_log else nice_ticks(lo, hi)


def render_static(parsed, title, x_title, y_title, x_eng, y_eng, x_log, y_log, fmt):
    fig, ax = plt.subplots(figsize=(8, 5))
    try:
        for label, ys in zip(parsed.y_labels, parsed.ys):
            ax.plot(parsed.x, ys, label=label)
        ax.set_title(title)
        ax.set_xlabel(x_title)
        ax.set_ylabel(y_title)
        ax.legend()
        if x_log:
            ax.set_xscale("log")
        if y_log:
            ax.set_yscale("log")
        xf = _formatter(x_eng)
        yf = _formatter(y_eng)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: xf(v)))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: yf(v)))
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, bbox_inches="tight")
        return buf.getvalue()
    finally:
        plt.close(fig)


def build_plotly_spec(parsed, title, x_title, y_title, x_eng, y_eng, x_log, y_log):
    xf = _formatter(x_eng)
    yf = _formatter(y_eng)

    traces = []
    for label, ys in zip(parsed.y_labels, parsed.ys):
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": label,
            "x": parsed.x,
            "y": ys,
            "customdata": [[xf(xv), yf(yv)] for xv, yv in zip(parsed.x, ys)],
            "hovertemplate": (
                f"{x_title}: %{{customdata[0]}}<br>"
                f"{y_title}: %{{customdata[1]}}<extra>%{{fullData.name}}</extra>"
            ),
        })

    x_ticks = _ticks(parsed.x, x_log)
    all_y = [v for ys in parsed.ys for v in ys]
    y_ticks = _ticks(all_y, y_log)

    xaxis = {
        "title": {"text": x_title},
        "tickvals": x_ticks,
        "ticktext": [xf(t) for t in x_ticks],
    }
    yaxis = {
        "title": {"text": y_title},
        "tickvals": y_ticks,
        "ticktext": [yf(t) for t in y_ticks],
    }
    if x_log:
        xaxis["type"] = "log"
    if y_log:
        yaxis["type"] = "log"

    layout = {"title": {"text": title}, "xaxis": xaxis, "yaxis": yaxis}
    return {"data": traces, "layout": layout}
