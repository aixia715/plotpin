import json
from dataclasses import asdict, dataclass

from app.parsing import CSVParseError, ParsedCSV


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
    if spec.x_log and any(v <= 0 for v in parsed.x):
        raise CSVParseError("X 轴含 ≤0 值,无法使用对数坐标")
    col_values = dict(zip(parsed.y_labels, parsed.ys))
    for pi, panel in enumerate(spec.panels):
        if not panel.y_log:
            continue
        for col, idx in spec.assign.items():
            if idx == pi and any(v <= 0 for v in col_values[col]):
                raise CSVParseError(f"面板 {pi + 1} 含 ≤0 值,无法使用对数坐标")


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
