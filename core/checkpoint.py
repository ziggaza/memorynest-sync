"""
SQLite-backed progress checkpoint for large-dataset resume support.

DB location: {dest_root}/.organizer/progress.db

Schema:
  progress  — one row per source file attempted
  sessions  — summary of each run (start time, end time, stats)

On resume: files with status IN ('moved','duplicate') are skipped entirely.
Files with status='error' are retried automatically.
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


_STATUS_DONE = frozenset({"moved", "duplicate"})


class Checkpoint:
    def __init__(self, db_path: Path, dry_run: bool = False) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._dry_run = dry_run
        # one connection per thread to avoid SQLite threading issues
        self._local = threading.local()
        self._create_tables()

    # ── public ────────────────────────────────────────────────────────────────

    def is_done(self, src_path: Path) -> bool:
        """Return True if this file was already successfully processed."""
        row = self._con.execute(
            "SELECT status FROM progress WHERE src_path = ?",
            (str(src_path),),
        ).fetchone()
        return bool(row and row[0] in _STATUS_DONE)

    def record(
        self,
        src_path: Path,
        status: str,               # 'moved' | 'duplicate' | 'error' | 'skipped'
        dest_path: Optional[Path] = None,
        error_msg: str = "",
    ) -> None:
        if self._dry_run:
            return   # do NOT pollute progress.db during a preview run
        self._con.execute(
            """
            INSERT INTO progress (src_path, status, dest_path, error_msg, processed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(src_path) DO UPDATE SET
                status       = excluded.status,
                dest_path    = excluded.dest_path,
                error_msg    = excluded.error_msg,
                processed_at = excluded.processed_at
            """,
            (
                str(src_path),
                status,
                str(dest_path) if dest_path else None,
                error_msg,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        self._con.commit()

    def count_done(self) -> int:
        row = self._con.execute(
            "SELECT COUNT(*) FROM progress WHERE status IN ('moved','duplicate')"
        ).fetchone()
        return row[0] if row else 0

    def start_session(self) -> int:
        cur = self._con.execute(
            "INSERT INTO sessions (started_at) VALUES (?)",
            (datetime.now().isoformat(timespec="seconds"),),
        )
        self._con.commit()
        return cur.lastrowid

    def end_session(self, session_id: int, stats: dict) -> None:
        import json
        self._con.execute(
            "UPDATE sessions SET ended_at = ?, stats_json = ? WHERE id = ?",
            (
                datetime.now().isoformat(timespec="seconds"),
                json.dumps(stats),
                session_id,
            ),
        )
        self._con.commit()

    def close(self) -> None:
        if hasattr(self._local, "con"):
            self._local.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── private ───────────────────────────────────────────────────────────────

    @property
    def _con(self) -> sqlite3.Connection:
        if not hasattr(self._local, "con"):
            con = sqlite3.connect(str(self._db_path))
            con.execute("PRAGMA journal_mode=WAL")   # safe for concurrent writers
            con.execute("PRAGMA synchronous=NORMAL")
            self._local.con = con
        return self._local.con

    def _create_tables(self) -> None:
        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS progress (
                src_path     TEXT PRIMARY KEY,
                status       TEXT NOT NULL,
                dest_path    TEXT,
                error_msg    TEXT DEFAULT '',
                processed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_status ON progress(status);

            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                ended_at   TEXT,
                stats_json TEXT
            );
        """)
        self._con.commit()
