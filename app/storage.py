import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.spec import ChartSpec


@dataclass
class Chart:
    id: str
    title: str
    created_at: str
    spec: ChartSpec


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
                    created_at TEXT NOT NULL,
                    spec_json TEXT NOT NULL
                )
                """
            )

    def csv_path(self, chart_id: str) -> Path:
        return self.csv_dir / f"{chart_id}.csv"

    def cache_path(self, chart_id: str, ext: str) -> Path:
        return self.cache_dir / f"{chart_id}.{ext}"

    def exists(self, chart_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM charts WHERE id = ?", (chart_id,)).fetchone()
            return row is not None

    def save_chart(self, chart_id: str, spec: ChartSpec, csv_bytes: bytes) -> Chart:
        created_at = datetime.now(timezone.utc).isoformat()
        self.csv_path(chart_id).write_bytes(csv_bytes)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO charts (id, title, created_at, spec_json) VALUES (?, ?, ?, ?)",
                (chart_id, spec.title, created_at, spec.to_json()),
            )
        return Chart(chart_id, spec.title, created_at, spec)

    def _row_to_chart(self, row: sqlite3.Row) -> Chart:
        return Chart(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            spec=ChartSpec.from_json(row["spec_json"]),
        )

    def get_chart(self, chart_id: str) -> Chart | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM charts WHERE id = ?", (chart_id,)).fetchone()
            return self._row_to_chart(row) if row else None

    def list_charts(self) -> list[Chart]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM charts ORDER BY created_at DESC, id DESC"
            ).fetchall()
            return [self._row_to_chart(r) for r in rows]

    def read_csv(self, chart_id: str) -> bytes:
        return self.csv_path(chart_id).read_bytes()

    def delete_chart(self, chart_id: str) -> bool:
        """彻底删除一条记录：DB 行 + CSV 源文件 + 全部缓存图。

        返回是否确有该记录被删除；不存在则返回 False。删除后对应的
        页面 / PNG / SVG / CSV 链接都会变成 404（issue 16，已与产品方确认）。
        """
        # 防御纵深：合法分享 id 仅含 [A-Za-z0-9]（见 ids.new_id）。路由层无鉴权，
        # 拒绝空串与路径遍历等非法输入，避免 csv_path / glob 逃出数据目录或误删 dotfile。
        if not (chart_id.isascii() and chart_id.isalnum()):
            return False
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM charts WHERE id = ?", (chart_id,))
            deleted = cur.rowcount > 0
        self.csv_path(chart_id).unlink(missing_ok=True)
        # 缓存文件名形如 {id}.thumb.png / {id}.png / {id}.svg，按精确前缀清理；
        # glob 的 "{id}." 不会误伤前缀相近的 id（del1 不波及 del10）。
        for f in self.cache_dir.glob(f"{chart_id}.*"):
            f.unlink(missing_ok=True)
        return deleted
