import json
from dataclasses import asdict, dataclass

from app.parsing import CSVParseError, ParsedCSV  # noqa: F401  (CSVParseError/ParsedCSV 供 validate_spec 使用)


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
