"""
Build the destination path for a media file.

Folder structure is driven by config["folder_structure"]["segments"],
an ordered list of tokens that can be reordered or toggled by the user.

Supported tokens:
  category  → "Photos" or "Videos"
  device    → device marketing name
  year      → "2024"
  month     → formatted month  (see month_format)
  day       → formatted day    (see day_format)

month_format options:
  "MM"            → "06"
  "MonthName"     → "June"
  "MM_MonthName"  → "06_June"   (default, sorts + readable)

day_format options:
  "DD"            → "15"
  "YYYY-MM-DD"    → "2024-06-15"

Conflict resolution: if filename exists at destination, append _1, _2, …
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from core.event_rules import load_rules, find_match

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

DEFAULT_SEGMENTS = ["category", "device", "year", "month"]


class PathBuilder:
    def __init__(self, config: dict) -> None:
        s = config.get("settings", {})
        self._dup_folder    = s.get("duplicate_folder_name","Duplicates")
        self._unread_folder = s.get("unreadable_folder_name","Unreadable")
        self._sep           = s.get("conflict_suffix_separator", "_")

        fs = config.get("folder_structure", {})
        self._segments        = fs.get("segments",           DEFAULT_SEGMENTS)
        self._month_fmt       = fs.get("month_format",       "MM_MonthName")
        self._day_fmt         = fs.get("day_format",         "YYYYMMDD")
        self._year_month_fmt  = fs.get("year_month_format",  "YYYY-MM")

        # category name → folder name (from categories config)
        self._cat_folders: dict[str, str] = {
            cat["name"]: cat.get("folder", cat["name"])
            for cat in config.get("categories", [])
        }
        # fallback: legacy photo_root / video_root from settings
        if "Photos" not in self._cat_folders:
            self._cat_folders["Photos"] = s.get("photo_root_name", "Photos")
        if "Videos" not in self._cat_folders:
            self._cat_folders["Videos"] = s.get("video_root_name", "Videos")

        # event rules ("Memory Mapper") — checked before normal segments
        self._event_rules = load_rules(config)
        self._events_root = s.get("events_root_name", "Events")

    # ── public ────────────────────────────────────────────────────────────────

    def build(
        self,
        dest_root: Path,
        media_type: str,        # "PHOTO" | "VIDEO"
        device_name: str,
        date: Optional[datetime],
        filename: str,
    ) -> Path:
        # Memory Mapper: if any user-defined event rule matches, route the
        # file into {dest_root}/{events_root}/{event.folder_name}/{filename}
        # — overriding the normal segment-based path.
        if self._event_rules:
            match = find_match(self._event_rules, date,
                               device=device_name, category=media_type)
            if match is not None:
                return dest_root / self._events_root / match.folder_name / filename

        # Default segment-based path
        path = dest_root
        for token in self._segments:
            part = self._render(token, media_type, device_name, date)
            if part:
                path = path / part
        return path / filename

    def build_duplicate(self, dest_root: Path, filename: str) -> Path:
        return dest_root / self._dup_folder / filename

    def build_unreadable(self, dest_root: Path, filename: str) -> Path:
        return dest_root / self._unread_folder / filename

    def resolve_conflict(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem, suffix, parent = path.stem, path.suffix, path.parent
        counter = 1
        while True:
            candidate = parent / f"{stem}{self._sep}{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    # ── private ───────────────────────────────────────────────────────────────

    def _render(
        self,
        token: str,
        media_type: str,
        device_name: str,
        date: Optional[datetime],
    ) -> str:
        if token == "category":
            return self._cat_folders.get(media_type, media_type)
        if token == "device":
            return device_name or "Unknown_Device"
        if token == "year":
            return str(date.year) if date else "Unknown_Year"
        if token == "month":
            return self._fmt_month(date)
        if token == "day":
            return self._fmt_day(date)
        if token == "year_month":
            return self._fmt_year_month(date)
        if token == "quarter":
            return self._fmt_quarter(date)
        return ""

    def _fmt_month(self, date: Optional[datetime]) -> str:
        if not date:
            return "Unknown_Month"
        m = date.month
        fmt = self._month_fmt
        if fmt == "MM":
            return f"{m:02d}"
        if fmt == "MonthName":
            return MONTH_NAMES[m]
        # default: MM_MonthName
        return f"{m:02d}_{MONTH_NAMES[m]}"

    def _fmt_quarter(self, date: Optional[datetime]) -> str:
        if not date:
            return "Unknown_Quarter"
        return f"Q{(date.month - 1) // 3 + 1}"

    def _fmt_year_month(self, date: Optional[datetime]) -> str:
        if not date:
            return "Unknown_YearMonth"
        if self._year_month_fmt == "YYYYMM":
            return date.strftime("%Y%m")
        if self._year_month_fmt == "YYYY_MM":
            return date.strftime("%Y_%m")
        return date.strftime("%Y-%m")  # default YYYY-MM

    def _fmt_day(self, date: Optional[datetime]) -> str:
        if not date:
            return "Unknown_Day"
        if self._day_fmt == "YYYYMMDD":
            return date.strftime("%Y%m%d")
        if self._day_fmt == "YYYY-MM-DD":
            return date.strftime("%Y-%m-%d")
        return f"{date.day:02d}"

    # ── preview helper (used by FolderStructureDialog) ────────────────────────

    def preview(self, media_type: str = "Photos", device: str = "iPhone 15 Pro",
                date: Optional[datetime] = None, filename: str = "IMG_001.JPG") -> str:
        if date is None:
            date = datetime(2024, 6, 15)
        dest = self.build(Path(""), media_type, device, date, filename)
        # strip the leading empty-path separator
        return str(dest).lstrip("\\/")
