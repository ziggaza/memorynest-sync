"""
Recursively scan source folders and yield media file paths.

Skips:
  - Hidden files/folders (starting with ".")
  - System files (Thumbs.db, .DS_Store, desktop.ini, *.txt, *.db)
  - The destination root itself (prevent scanning own output)
"""

import os
from pathlib import Path
from typing import Generator, Sequence

_SKIP_NAMES = frozenset({
    "thumbs.db", ".ds_store", "desktop.ini",
    ".nomedia", "picasa.ini", ".picasa.ini",
})

_SKIP_EXTENSIONS = frozenset({
    ".txt", ".db", ".ini", ".xml", ".json",
    ".lnk", ".url", ".nfo", ".log",
})


def scan(
    sources: Sequence[Path],
    config: dict,
    dest_root: Path | None = None,
) -> Generator[Path, None, None]:
    """
    Yield every media file found in *sources* (recursively).
    Skips the dest_root tree to avoid scanning already-organized files.
    """
    from core.classifier import classify, UNKNOWN

    seen_dirs: set[Path] = set()
    dest_resolved = dest_root.resolve() if dest_root else None

    for source in sources:
        source = Path(source).resolve()
        if not source.exists():
            continue

        for root, dirs, files in os.walk(source, followlinks=False):
            root_path = Path(root)

            # skip destination folder
            if dest_resolved and _is_under(root_path, dest_resolved):
                dirs.clear()
                continue

            # skip hidden / system dirs in-place (modifies dirs to prune walk)
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and d.lower() not in _SKIP_NAMES
            ]

            for fname in files:
                if fname.startswith("."):
                    continue
                if fname.lower() in _SKIP_NAMES:
                    continue

                fpath = root_path / fname

                if fpath.suffix.lower() in _SKIP_EXTENSIONS:
                    continue

                # yield only recognised media
                if classify(fpath, config) != UNKNOWN:
                    yield fpath


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
