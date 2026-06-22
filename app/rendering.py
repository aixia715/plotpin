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


def _yaxis_key(idx: int) -> str:
    return "yaxis" if idx == 0 else f"yaxis{idx + 1}"


def _yref(idx: int) -> str:
    return "y" if idx == 0 else f"y{idx + 1}"


def _panel_domains(n: int, gap: float = 0.08) -> list[tuple[float, float]]:
    # 面板 0 在顶部；返回每个面板的 [bottom, top]
    h = (1 - gap * (n - 1)) / n
    domains = []
    for i in range(n):
        top = 1 - i * (h + gap)
        domains.append((top - h, top))
    return domains


def build_plotly_spec(parsed, spec):
    xf = _formatter(spec.x_eng)
    col_values = dict(zip(parsed.y_labels, parsed.ys))
    n = len(spec.panels)
    domains = _panel_domains(n)

    traces = []
    for col, idx in spec.assign.items():
        if idx is None:
            continue
        panel = spec.panels[idx]
        yf = _formatter(panel.y_eng)
        ys = col_values[col]
        traces.append({
            "type": "scatter",
            "mode": "lines",
            "name": col,
            "x": parsed.x,
            "y": ys,
            "yaxis": _yref(idx),
            "customdata": [[xf(xv), yf(yv)] for xv, yv in zip(parsed.x, ys)],
            "hovertemplate": (
                f"{spec.x_title}: %{{customdata[0]}}<br>"
                f"{panel.y_title}: %{{customdata[1]}}<extra>%{{fullData.name}}</extra>"
            ),
        })

    x_ticks = _ticks(parsed.x, spec.x_log)
    bottom_ref = _yref(n - 1)
    xaxis = {
        "title": {"text": spec.x_title},
        "tickvals": x_ticks,
        "ticktext": [xf(t) for t in x_ticks],
        "anchor": bottom_ref,
    }
    if spec.x_log:
        xaxis["type"] = "log"

    layout = {"title": {"text": spec.title}, "xaxis": xaxis}
    for idx, panel in enumerate(spec.panels):
        yf = _formatter(panel.y_eng)
        members = [col_values[c] for c, i in spec.assign.items() if i == idx]
        flat = [v for ys in members for v in ys] or [0.0, 1.0]
        y_ticks = _ticks(flat, panel.y_log)
        ax = {
            "title": {"text": panel.y_title},
            "tickvals": y_ticks,
            "ticktext": [yf(t) for t in y_ticks],
            "domain": list(domains[idx]),
            "anchor": "x",
        }
        if panel.y_log:
            ax["type"] = "log"
        layout[_yaxis_key(idx)] = ax

    return {"data": traces, "layout": layout}
