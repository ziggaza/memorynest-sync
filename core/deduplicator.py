"""
Hash-based duplicate detection with SQLite cache.

Strategy:
  1. xxHash (fast, non-cryptographic) for all files.
  2. If a hash collision is found, compare file sizes first — different
     size means different file (hash collision is impossible with xxHash
     for same content, but guards logic clearly).
  3. The SQLite DB persists hash → first-seen-path so repeated runs
     don't re-hash already processed files.

DB location: {dest_root}/.organizer/hashes.db
"""

import sqlite3
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import xxhash

logger = logging.getLogger(__name__)

CHUNK = 1024 * 1024  # 1 MB read chunks


@dataclass
class DupeResult:
    is_duplicate: bool
    original_path: Optional[str] = None  # path of the first-seen copy
    file_hash: str = ""


class Deduplicator:
    def __init__(self, db_path: Path, dry_run: bool = False) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(db_path))
        self._dry_run = dry_run
        # In-memory mirror used during dry run so that within-run duplicates
        # are still detected without polluting hashes.db on disk.
        self._mem: dict[tuple[str, int], str] = {}
        self._create_tables()

    # ── public ────────────────────────────────────────────────────────────────

    def check(self, path: Path) -> DupeResult:
        """
        Hash the file, look up the DB (and in-memory cache during dry run).
        Returns DupeResult(is_duplicate=True/False, ...).
        """
        file_hash = self._hash_file(path)
        size = path.stat().st_size
        spath = str(path)

        # 1. check persistent DB (always — so cross-run history still works)
        existing = self._lookup(file_hash, size)
        # 2. in dry run: also check in-memory hashes from earlier in this run
        if not existing and self._dry_run:
            existing = self._mem.get((file_hash, size))

        if existing and existing != spath:
            return DupeResult(is_duplicate=True, original_path=existing, file_hash=file_hash)

        # new file — record it (memory only during dry run, DB otherwise)
        if self._dry_run:
            self._mem[(file_hash, size)] = spath
        else:
            self._insert(file_hash, size, spath)
        return DupeResult(is_duplicate=False, file_hash=file_hash)

    def update_path(self, file_hash: str, old_path: str, new_path: str) -> None:
        """Call after a file is moved to keep the DB path current."""
        if self._dry_run:
            return   # nothing was persisted — nothing to update
        self._con.execute(
            "UPDATE hashes SET path = ? WHERE hash = ? AND path = ?",
            (new_path, file_hash, old_path),
        )
        self._con.commit()

    def close(self) -> None:
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── private ───────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        self._con.execute("""
            CREATE TABLE IF NOT EXISTS hashes (
                hash TEXT NOT NULL,
                size INTEGER NOT NULL,
                path TEXT NOT NULL,
                PRIMARY KEY (hash, size)
            )
        """)
        self._con.commit()

    def _lookup(self, file_hash: str, size: int) -> Optional[str]:
        row = self._con.execute(
            "SELECT path FROM hashes WHERE hash = ? AND size = ?",
            (file_hash, size),
        ).fetchone()
        return row[0] if row else None

    def _insert(self, file_hash: str, size: int, path: str) -> None:
        self._con.execute(
            "INSERT OR IGNORE INTO hashes (hash, size, path) VALUES (?, ?, ?)",
            (file_hash, size, path),
        )
        self._con.commit()

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = xxhash.xxh64()
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK):
                h.update(chunk)
        return h.hexdigest()
