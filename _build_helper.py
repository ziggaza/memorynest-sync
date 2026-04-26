"""Tiny build-time helper for build_installer.bat.

Single source of truth for things the .bat needs (version detection,
installer.iss rewrites, the canonical clean default config). Doing this
in pure Python avoids the quote-escaping nightmare of Windows .bat
'for /f' loops, which silently broke earlier versions.

Subcommands:

    python _build_helper.py version
        -> prints APP_VERSION from main.py to stdout, exits 0

    python _build_helper.py update-iss <version>
        -> rewrites installer.iss AppVersion= and OutputBaseFilename=

    python _build_helper.py clean-config
        -> writes config.default.json with the canonical FRESH-INSTALL
           state. Idempotent: running it overwrites whatever is there
           with the deterministic factory baseline. This is what every
           build_installer.bat run executes BEFORE pyinstaller bundles
           the app, so the shipped installer NEVER carries a developer's
           live device mappings, event rules, or auto-detected pollution.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


# ── canonical clean default config ───────────────────────────────────────────
# Source of truth for what a fresh install looks like.  device_mappings is
# intentionally empty: the device_resolver auto-detects every camera/phone
# from EXIF on first scan and writes the raw "Make Model" name into the
# mapping with auto_detected_keys flagging it for the user to rename via
# Device Manager.  Pre-shipping a curated list saved zero typing for users
# whose hardware wasn't on it, and leaked the developer's hardware list
# into every installer download.

_CLEAN_CATEGORIES = [
    {
        "name":       "Photos",
        "folder":     "Photos",
        "media_hint": "photo",
        "built_in":   True,
        "extensions": [
            ".3fr", ".arw", ".avif", ".bmp", ".cap", ".cr2", ".cr3", ".dng",
            ".erf", ".fff", ".gif", ".gpr", ".heic", ".heif", ".iiq",
            ".jpeg", ".jpg", ".jxl", ".kdc", ".mrw", ".nef", ".nrw", ".orf",
            ".pef", ".png", ".ptx", ".pxn", ".raf", ".raw", ".rw2", ".rwl",
            ".sr2", ".srf", ".srw", ".tif", ".tiff", ".webp", ".x3f",
        ],
    },
    {
        "name":       "Videos",
        "folder":     "Videos",
        "media_hint": "video",
        "built_in":   True,
        "extensions": [
            ".3g2", ".3gp", ".ari", ".avi", ".braw", ".divx", ".f4v",
            ".flv", ".insv", ".m2ts", ".m2v", ".m4v", ".mkv", ".mov",
            ".mp4", ".mpeg", ".mpg", ".mts", ".mxf", ".r3d", ".ts",
            ".vob", ".webm", ".wmv", ".xvid",
        ],
    },
]

_CLEAN_SETTINGS = {
    "month_format":              "MM_MonthName",
    "unknown_device_folder":     "Unknown_Device",
    "fallback_strategy":         "use_file_date",
    "conflict_suffix_separator": "_",
    "duplicate_folder_name":     "Duplicates",
    "unreadable_folder_name":    "Unreadable",
    "events_root_name":          "Events",
}

_CLEAN_FOLDER_STRUCTURE = {
    "segments":          ["category", "device", "year", "month"],
    "month_format":      "MM_MonthName",
    "year_month_format": "YYYY-MM",
    "day_format":        "YYYYMMDD",
}


def _clean_config() -> dict:
    """The canonical baseline. Plain dict so the JSON file is deterministic."""
    return {
        "device_mappings":    {},                       # blank — auto-fills
        "categories":         _CLEAN_CATEGORIES,
        "settings":           _CLEAN_SETTINGS,
        "auto_detected_keys": [],
        "folder_structure":   _CLEAN_FOLDER_STRUCTURE,
        "event_rules":        [],
    }


# ── command implementations ──────────────────────────────────────────────────

def get_version() -> str:
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    if not match:
        raise RuntimeError("APP_VERSION not found in main.py")
    return match.group(1)


def update_installer(version: str) -> None:
    iss = ROOT / "installer.iss"
    text = iss.read_text(encoding="utf-8")
    text = re.sub(r"^AppVersion=.*$",
                  f"AppVersion={version}", text, flags=re.M)
    text = re.sub(r"^OutputBaseFilename=.*$",
                  f"OutputBaseFilename=MemoryNestSync_Setup_v{version}",
                  text, flags=re.M)
    iss.write_text(text, encoding="utf-8")


def write_clean_config() -> Path:
    target = ROOT / "config.default.json"
    target.write_text(
        json.dumps(_clean_config(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: _build_helper.py {version|update-iss <version>|clean-config}",
              file=sys.stderr)
        return 2
    cmd = argv[1]
    try:
        if cmd == "version":
            print(get_version())
            return 0
        if cmd == "update-iss":
            if len(argv) < 3:
                print("ERROR: update-iss requires a version argument",
                      file=sys.stderr)
                return 2
            update_installer(argv[2])
            print(f"installer.iss updated to v{argv[2]}")
            return 0
        if cmd == "clean-config":
            target = write_clean_config()
            cfg = _clean_config()
            print(f"Wrote {target.name}: {target.stat().st_size:,} bytes")
            print(f"  device_mappings:    {len(cfg['device_mappings'])} entries (blank)")
            print(f"  categories:         {len(cfg['categories'])} (built-in Photos+Videos)")
            print(f"  auto_detected_keys: {len(cfg['auto_detected_keys'])}")
            print(f"  event_rules:        {len(cfg['event_rules'])}")
            return 0
        print(f"ERROR: unknown command '{cmd}'", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
