import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Chart:
    id: str
    title: str
    x_title: str
    y_title: str
    x_eng: bool
    y_eng: bool
    x_log: bool
    y_log: bool
    created_at: str


class Storage:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.csv_dir = self.data_dir / "csv"
        self.cache_dir = self.data_dir / "cache"
        self.db_path = self.data_dir / "plotpin.db"
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS charts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    x_title TEXT NOT NULL,
                    y_title TEXT NOT NULL,
                    x_eng INTEGER NOT NULL,
                    y_eng INTEGER NOT NULL,
                    x_log INTEGER NOT NULL,
                    y_log INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def csv_path(self, chart_id: str) -> Path:
        return self.csv_dir / f"{chart_id}.csv"

    def cache_path(self, chart_id: str, ext: str) -> Path:
        return self.cache_dir / f"{chart_id}.{ext}"

    def exists(self, chart_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM charts WHERE id = ?", (chart_id,)
            ).fetchone()
            return row is not None

    def save_chart(self, chart_id, title, x_title, y_title, x_eng, y_eng, x_log, y_log, csv_bytes) -> Chart:
        created_at = datetime.now(timezone.utc).isoformat()
        self.csv_path(chart_id).write_bytes(csv_bytes)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO charts
                    (id, title, x_title, y_title, x_eng, y_eng, x_log, y_log, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (chart_id, title, x_title, y_title,
                 int(x_eng), int(y_eng), int(x_log), int(y_log), created_at),
            )
        return Chart(chart_id, title, x_title, y_title,
                     bool(x_eng), bool(y_eng), bool(x_log), bool(y_log), created_at)

    def _row_to_chart(self, row: sqlite3.Row) -> Chart:
        return Chart(
            id=row["id"],
            title=row["title"],
            x_title=row["x_title"],
            y_title=row["y_title"],
            x_eng=bool(row["x_eng"]),
            y_eng=bool(row["y_eng"]),
            x_log=bool(row["x_log"]),
            y_log=bool(row["y_log"]),
            created_at=row["created_at"],
        )

    def get_chart(self, chart_id: str) -> Chart | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM charts WHERE id = ?", (chart_id,)
            ).fetchone()
            return self._row_to_chart(row) if row else None

    def list_charts(self) -> list[Chart]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM charts ORDER BY created_at DESC, id DESC"
            ).fetchall()
            return [self._row_to_chart(r) for r in rows]

    def read_csv(self, chart_id: str) -> bytes:
        return self.csv_path(chart_id).read_bytes()
