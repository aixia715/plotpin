import io

import matplotlib

matplotlib.use("Agg")  # 无头环境,必须在 pyplot 之前设置

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from app.eng_notation import format_eng, format_plain, log_ticks, nice_ticks  # noqa: E402
from app.parsing import ParsedCSV  # noqa: E402
from app.spec import ChartSpec, LogFilterReport, apply_log_filter  # noqa: E402

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
    vals = [v for v in values if v is not None]
    lo, hi = min(vals), max(vals)
    return log_ticks(lo, hi) if use_log else nice_ticks(lo, hi)


def _log_warning_text(report: LogFilterReport) -> str:
    if report.x_dropped and report.y_dropped:
        return "对数 X 轴和 Y 轴包含 ≤0 的值，已自动忽略"
    if report.x_dropped:
        return "对数 X 轴包含 ≤0 的值，已自动忽略"
    if report.y_dropped:
        return "对数 Y 轴包含 ≤0 的值，已自动忽略"
    return ""


def render_static(parsed, spec, fmt):
    parsed, _report = apply_log_filter(parsed, spec)
    col_values = dict(zip(parsed.y_labels, parsed.ys))
    n = len(spec.panels)
    fig, axes = plt.subplots(n, 1, figsize=(8, max(3, 2.6 * n)), sharex=True, squeeze=False)
    axes = [row[0] for row in axes]
    try:
        for idx, panel in enumerate(spec.panels):
            ax = axes[idx]
            for col, i in spec.assign.items():
                if i == idx:
                    ys_plot = [float("nan") if v is None else v for v in col_values[col]]
                    ax.plot(parsed.x, ys_plot, label=col)
            ax.set_ylabel(panel.y_title)
            ax.legend()
            if panel.y_log:
                ax.set_yscale("log")
            yf = _formatter(panel.y_eng)
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos, f=yf: f(v)))
        axes[0].set_title(spec.title)
        bottom = axes[-1]
        bottom.set_xlabel(spec.x_title)
        if spec.x_log:
            bottom.set_xscale("log")
        xf = _formatter(spec.x_eng)
        bottom.xaxis.set_major_formatter(FuncFormatter(lambda v, _pos: xf(v)))
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
    parsed, report = apply_log_filter(parsed, spec)
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
            "customdata": [
                [xf(xv), (yf(yv) if yv is not None else None)]
                for xv, yv in zip(parsed.x, ys)
            ],
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
        panel_cols = [col_values[c] for c, i in spec.assign.items() if i == idx]
        flat = [v for ys in panel_cols for v in ys] or [0.0, 1.0]
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

    return {"data": traces, "layout": layout, "warning": _log_warning_text(report)}
