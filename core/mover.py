"""
Orchestrator: scanner → classifier → metadata → resolver → deduplicator → move.

New in Phase 5:
  • Checkpoint / resume  — skip files already processed in a previous run
  • Multi-threaded metadata extraction  — parallel EXIF/video-meta reading
  • Filename-based device inference  — fallback when metadata has no device info
  • Per-file progress events include estimated speed (files/s)
"""

import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional, Sequence

from core.classifier import classify, UNKNOWN
from core.checkpoint import Checkpoint
from core.deduplicator import Deduplicator
from core.device_resolver import DeviceResolver
from core.filename_guesser import guess_device
from core.metadata import extract
from core.path_builder import PathBuilder
from core.scanner import scan

logger = logging.getLogger(__name__)


# ── event model ───────────────────────────────────────────────────────────────

class EventKind(Enum):
    SCANNED   = auto()
    PROGRESS  = auto()
    RESUMED   = auto()   # emitted once when resume skips files
    DONE      = auto()


@dataclass
class OrganizerEvent:
    kind: EventKind
    total: int = 0
    already_done: int = 0    # files skipped via resume
    index: int = 0
    src_path: str = ""
    dest_path: str = ""
    status: str = ""         # moved | copied | duplicate | dry_run | error | skipped | resumed
    device: str = ""
    date_source: str = ""
    media_type: str = ""     # "PHOTO" | "VIDEO" — for accurate GUI counting
    error_msg: str = ""
    files_per_sec: float = 0.0
    stats: dict = field(default_factory=dict)


# ── stats ─────────────────────────────────────────────────────────────────────

@dataclass
class Stats:
    total: int = 0
    moved: int = 0
    duplicates: int = 0
    errors: int = 0
    skipped: int = 0
    resumed: int = 0
    elapsed_sec: float = 0.0

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ── pre-fetch result ──────────────────────────────────────────────────────────

@dataclass
class _FileMeta:
    path: Path
    media_type: str     # category name e.g. "Photos"/"Videos"/custom, or UNKNOWN
    device: str
    date_source: str
    date: object        # datetime | None
    error: Optional[str] = None


# ── organizer ─────────────────────────────────────────────────────────────────

class Organizer:
    def __init__(
        self,
        config: dict,
        dest_root: Path,
        dry_run: bool = True,
        copy_mode: bool = False,   # True = copy, False = move
        resume: bool = True,
        workers: int = 4,
        on_event: Optional[Callable[[OrganizerEvent], None]] = None,
    ) -> None:
        self._config = config
        self._dest_root = dest_root
        self._dry_run = dry_run
        self._copy_mode = copy_mode
        self._resume = resume
        self._workers = max(1, workers)
        self._on_event = on_event or (lambda e: None)
        self._resolver = DeviceResolver(config)
        self._builder = PathBuilder(config)
        self._stop_flag = False

    # ── public ────────────────────────────────────────────────────────────────

    def stop(self) -> None:
        self._stop_flag = True

    def run(self, sources: Sequence[Path]) -> Stats:
        self._stop_flag = False
        stats = Stats()
        t0 = time.monotonic()

        db_dir = self._dest_root / ".organizer"
        hash_db = db_dir / "hashes.db"
        ckpt_db = db_dir / "progress.db"

        with Deduplicator(hash_db, dry_run=self._dry_run) as dedup, \
             Checkpoint(ckpt_db, dry_run=self._dry_run) as ckpt:
            session_id = ckpt.start_session()

            # ── 1. scan ──────────────────────────────────────────────────────
            all_files = list(scan(sources, self._config, self._dest_root))
            stats.total = len(all_files)

            # ── 2. resume filter ─────────────────────────────────────────────
            if self._resume:
                pending = [f for f in all_files if not ckpt.is_done(f)]
                already_done = len(all_files) - len(pending)
            else:
                pending = all_files
                already_done = 0

            stats.resumed = already_done
            self._emit(OrganizerEvent(
                kind=EventKind.SCANNED,
                total=stats.total,
                already_done=already_done,
            ))
            if already_done:
                self._emit(OrganizerEvent(
                    kind=EventKind.RESUMED,
                    total=stats.total,
                    already_done=already_done,
                ))

            # ── 3. parallel metadata extraction ──────────────────────────────
            meta_map = self._prefetch_metadata(pending)

            # ── 4. serial move loop ───────────────────────────────────────────
            processed = already_done
            for src in pending:
                if self._stop_flag:
                    break
                processed += 1
                fm = meta_map.get(src)
                elapsed = time.monotonic() - t0
                fps = processed / elapsed if elapsed > 0 else 0.0
                self._process(src, processed, stats, dedup, ckpt, fm, fps)

            stats.elapsed_sec = time.monotonic() - t0
            ckpt.end_session(session_id, stats.to_dict())

        self._emit(OrganizerEvent(
            kind=EventKind.DONE,
            total=stats.total,
            stats=stats.to_dict(),
        ))
        logger.info(
            "Done. moved=%d dupes=%d resumed=%d errors=%d elapsed=%.1fs @ %.1f files/s",
            stats.moved, stats.duplicates, stats.resumed,
            stats.errors, stats.elapsed_sec,
            stats.total / stats.elapsed_sec if stats.elapsed_sec > 0 else 0,
        )
        return stats

    # ── private: metadata prefetch ────────────────────────────────────────────

    def _prefetch_metadata(self, files: list[Path]) -> dict[Path, "_FileMeta"]:
        result: dict[Path, _FileMeta] = {}
        if not files:
            return result

        def _fetch(path: Path) -> _FileMeta:
            media_type = classify(path, self._config)
            if media_type == UNKNOWN:
                return _FileMeta(path=path, media_type=UNKNOWN,
                                 device="", date_source="", date=None)
            try:
                hint = next(
                    (c.get("media_hint", "photo")
                     for c in self._config.get("categories", [])
                     if c["name"] == media_type),
                    "photo",
                )
                meta = extract(path, hint)
                # device: EXIF → filename guess → Unknown_Device
                if meta.make or meta.model:
                    device = self._resolver.resolve(meta.make, meta.model)
                else:
                    guessed = guess_device(path)
                    if guessed:
                        device = guessed
                    else:
                        device = self._resolver.resolve(None, None)
                return _FileMeta(
                    path=path,
                    media_type=media_type,
                    device=device,
                    date_source=meta.date_source,
                    date=meta.date,
                    error=meta.error,
                )
            except Exception as e:
                return _FileMeta(path=path, media_type=media_type,
                                 device="Unknown_Device", date_source="error",
                                 date=None, error=str(e))

        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = {pool.submit(_fetch, f): f for f in files}
            for future in as_completed(futures):
                fm = future.result()
                result[fm.path] = fm
                if self._stop_flag:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

        return result

    # ── private: process one file ─────────────────────────────────────────────

    def _process(
        self,
        src: Path,
        idx: int,
        stats: Stats,
        dedup: Deduplicator,
        ckpt: Checkpoint,
        fm: Optional["_FileMeta"],
        fps: float,
    ) -> None:
        evt = OrganizerEvent(
            kind=EventKind.PROGRESS,
            index=idx,
            src_path=str(src),
            files_per_sec=round(fps, 1),
        )

        try:
            if fm is None or fm.media_type == UNKNOWN:
                evt.status = "skipped"
                stats.skipped += 1
                ckpt.record(src, "skipped")
                self._emit(evt)
                return

            evt.device = fm.device
            evt.date_source = fm.date_source
            evt.media_type = fm.media_type   # category name string

            # duplicate check
            dupe = dedup.check(src)
            if dupe.is_duplicate:
                dest = self._builder.build_duplicate(self._dest_root, src.name)
                dest = self._builder.resolve_conflict(dest)
                evt.dest_path = str(dest)
                evt.status = "duplicate"
                stats.duplicates += 1
                logger.info("DUPE  %s  (original: %s)", src.name, dupe.original_path)
                if not self._dry_run:
                    self._do_transfer(src, dest)
                ckpt.record(src, "duplicate", dest)
                self._emit(evt)
                return

            # build destination
            dest = self._builder.build(
                self._dest_root, fm.media_type, fm.device, fm.date, src.name
            )
            dest = self._builder.resolve_conflict(dest)
            evt.dest_path = str(dest)

            if self._dry_run:
                evt.status = "dry_run"
                logger.info("DRY   %s  =>  %s", src, dest)
            else:
                self._do_transfer(src, dest)
                dedup.update_path(dupe.file_hash, str(src), str(dest))
                op = "copy" if self._copy_mode else "moved"
                ckpt.record(src, op, dest)
                evt.status = op
                logger.info("%s  %s  =>  %s",
                            "COPY" if self._copy_mode else "MOVE", src, dest)

            stats.moved += 1

        except Exception as exc:
            evt.status = "error"
            evt.error_msg = str(exc)
            stats.errors += 1
            ckpt.record(src, "error", error_msg=str(exc))
            logger.exception("ERROR processing %s: %s", src, exc)

        self._emit(evt)

    def _do_transfer(self, src: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if self._copy_mode:
            shutil.copy2(str(src), str(dest))
        else:
            shutil.move(str(src), str(dest))

    def _emit(self, event: OrganizerEvent) -> None:
        try:
            self._on_event(event)
        except Exception:
            pass
