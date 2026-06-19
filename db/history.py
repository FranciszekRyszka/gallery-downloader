"""SQLite-backed download history and state persistence."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "logs" / "history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS galleries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL UNIQUE,
    title        TEXT,
    dest_dir     TEXT,
    image_count  INTEGER DEFAULT 0,
    downloaded   INTEGER DEFAULT 0,
    failed       INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'pending',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""


@dataclass
class HistoryEntry:
    id: int
    url: str
    title: str
    dest_dir: str
    image_count: int
    downloaded: int
    failed: int
    status: str
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class History:
    """Thin wrapper around the SQLite history database."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def record_start(
        self, url: str, title: str, dest_dir: str, image_count: int
    ) -> int:
        """Insert (or refresh) a gallery row and return its id."""
        now = _now()
        cur = self.conn.execute(
            """
            INSERT INTO galleries
                (url, title, dest_dir, image_count, downloaded, failed,
                 status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0, 0, 'in_progress', ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                dest_dir=excluded.dest_dir,
                image_count=excluded.image_count,
                status='in_progress',
                updated_at=excluded.updated_at
            """,
            (url, title, dest_dir, image_count, now, now),
        )
        self.conn.commit()
        if cur.lastrowid:
            row = self.conn.execute(
                "SELECT id FROM galleries WHERE url = ?", (url,)
            ).fetchone()
            return int(row["id"])
        row = self.conn.execute(
            "SELECT id FROM galleries WHERE url = ?", (url,)
        ).fetchone()
        return int(row["id"])

    def update_progress(
        self, gallery_id: int, *, downloaded: int, failed: int
    ) -> None:
        self.conn.execute(
            "UPDATE galleries SET downloaded=?, failed=?, updated_at=? "
            "WHERE id=?",
            (downloaded, failed, _now(), gallery_id),
        )
        self.conn.commit()

    def record_finish(self, gallery_id: int, status: str = "complete") -> None:
        self.conn.execute(
            "UPDATE galleries SET status=?, updated_at=? WHERE id=?",
            (status, _now(), gallery_id),
        )
        self.conn.commit()

    def all_entries(self) -> list[HistoryEntry]:
        rows = self.conn.execute(
            "SELECT * FROM galleries ORDER BY updated_at DESC"
        ).fetchall()
        return [HistoryEntry(**dict(row)) for row in rows]

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "History":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
