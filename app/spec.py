import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.parsing import CSVParseError, ParsedCSV


def filename_stem(name: str | None) -> str:
    """从文件名取不含扩展名的主名；缺失或为空时兜底返回 `chart`。"""
    if not name:
        return "chart"
    stem = Path(name).stem.lstrip(".")
    return stem or "chart"


def auto_titles(filename: str | None, parsed: ParsedCSV) -> tuple[str, str]:
    """自动派生图表标题（文件名主名）与 X 轴标题（首列表头）。"""
    return filename_stem(filename), parsed.x_label


def auto_panel_y_title(
    panel_index: int, assign: dict[str, int | None], y_labels: list[str]
) -> str:
    """面板 Y 轴标题的自动兜底：取分配到该面板的第一条曲线列表头；无则 `Y`。"""
    for label in y_labels:
        if assign.get(label) == panel_index:
            return label
    return "Y"


@dataclass
class PanelSpec:
    y_title: str
    y_eng: bool
    y_log: bool


@dataclass
class ChartSpec:
    title: str
    x_title: str
    x_eng: bool
    x_log: bool
    panels: list[PanelSpec]
    assign: dict[str, int | None]

    def to_json(self) -> str:
        return json.dumps(
            {
                "title": self.title,
                "x_title": self.x_title,
                "x_eng": self.x_eng,
                "x_log": self.x_log,
                "panels": [asdict(p) for p in self.panels],
                "assign": self.assign,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, s: str) -> "ChartSpec":
        d = json.loads(s)
        return cls(
            title=d["title"],
            x_title=d["x_title"],
            x_eng=bool(d["x_eng"]),
            x_log=bool(d["x_log"]),
            panels=[
                PanelSpec(p["y_title"], bool(p["y_eng"]), bool(p["y_log"]))
                for p in d["panels"]
            ],
            assign={k: (None if v is None else int(v)) for k, v in d["assign"].items()},
        )


@dataclass
class LogFilterReport:
    x_dropped: bool = False
    y_dropped: bool = False


def apply_log_filter(
    parsed: ParsedCSV, spec: ChartSpec
) -> tuple[ParsedCSV, LogFilterReport]:
    x = list(parsed.x)
    ys = [list(col) for col in parsed.ys]
    x_dropped = False
    y_dropped = False

    # 共享 X 对数轴：删除 x ≤ 0 的整行
    if spec.x_log:
        keep = [i for i, v in enumerate(x) if v is not None and v > 0]
        if len(keep) != len(x):
            x_dropped = True
        if not keep:
            raise CSVParseError("X 轴所有值 ≤0，无法使用对数坐标")
        x = [x[i] for i in keep]
        ys = [[col[i] for i in keep] for col in ys]

    # 每个对数面板：分配到它的列里 ≤0 的点置 None（缺口）
    col_index = {label: i for i, label in enumerate(parsed.y_labels)}
    for pi, panel in enumerate(spec.panels):
        if not panel.y_log:
            continue
        panel_cols = [c for c, idx in spec.assign.items() if idx == pi]
        any_positive = False
        for c in panel_cols:
            col = ys[col_index[c]]
            for j, v in enumerate(col):
                if v is None:
                    continue
                if v <= 0:
                    col[j] = None
                    y_dropped = True
                else:
                    any_positive = True
        if panel_cols and not any_positive:
            raise CSVParseError(f"面板 {pi + 1} 所有值 ≤0，无法使用对数坐标")

    filtered = ParsedCSV(parsed.x_label, x, list(parsed.y_labels), ys)
    return filtered, LogFilterReport(x_dropped, y_dropped)


def validate_spec(spec: ChartSpec, parsed: ParsedCSV) -> None:
    if not spec.panels:
        raise CSVParseError("至少需要一个面板")
    if set(spec.assign.keys()) != set(parsed.y_labels):
        raise CSVParseError("曲线分配与数据列不一致")
    n = len(spec.panels)
    for col, idx in spec.assign.items():
        if idx is not None and not (0 <= idx < n):
            raise CSVParseError(f"曲线 `{col}` 指派到不存在的面板")
    if all(idx is None for idx in spec.assign.values()):
        raise CSVParseError("至少需要显示一条曲线")
    for pi in range(len(spec.panels)):
        if not any(idx == pi for idx in spec.assign.values()):
            raise CSVParseError(f"面板 {pi + 1} 没有分配任何曲线")
    # 对数轴 ≤0：部分剔除不报错，仅"全 ≤0"在此触发拒绝
    apply_log_filter(parsed, spec)


def default_spec(
    parsed: ParsedCSV,
    title: str,
    x_title: str,
    x_eng: bool = False,
    x_log: bool = False,
) -> ChartSpec:
    """省略 layout 时的单面板默认配置：所有 Y 列指派到唯一面板。"""
    return ChartSpec(
        title=title,
        x_title=x_title,
        x_eng=bool(x_eng),
        x_log=bool(x_log),
        panels=[PanelSpec(parsed.y_labels[0], False, False)],
        assign={label: 0 for label in parsed.y_labels},
    )
