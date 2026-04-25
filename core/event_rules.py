"""
Event-based folder rules — the "Memory Mapper" feature.

When a media file's capture date falls within a user-defined event window,
that file is routed into a single named folder (e.g. "HBD Party OOM 2025")
instead of the default segment-based hierarchy. Optional device / category
filters narrow when a rule applies; priority breaks ties on overlap.

Stored in `config.json` under the `event_rules` key:

    "event_rules": [
        {
            "name":        "HBD OOM 2025",
            "start":       "2025-06-17T00:00:00",
            "end":         "2025-06-20T23:59:59",
            "folder_name": "HBD PARTY OOM 2025",
            "devices":     ["iPhone 15 Pro"],   // empty list = any
            "categories":  ["Photos"],          // empty list = any
            "priority":    100,
            "enabled":     true
        }
    ]

Datetimes use ISO-8601; `.fromisoformat()` accepts both date and datetime.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Iterable, Optional


@dataclass
class EventRule:
    name:        str
    start:       datetime
    end:         datetime
    folder_name: str
    devices:     list[str] = field(default_factory=list)
    categories:  list[str] = field(default_factory=list)
    priority:    int       = 0
    enabled:     bool      = True

    # ── (de)serialisation ─────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, d: dict) -> "EventRule":
        return cls(
            name        = d.get("name", "Untitled event"),
            start       = _parse_dt(d.get("start", ""), default=datetime.min),
            end         = _parse_dt(d.get("end",   ""), default=datetime.max),
            folder_name = d.get("folder_name", "Untitled"),
            devices     = list(d.get("devices",    [])),
            categories  = list(d.get("categories", [])),
            priority    = int(d.get("priority", 0)),
            enabled     = bool(d.get("enabled", True)),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat(timespec="seconds")
        d["end"]   = self.end.isoformat(timespec="seconds")
        return d

    # ── matching ──────────────────────────────────────────────────────────────

    def matches(
        self,
        date:     Optional[datetime],
        device:   str = "",
        category: str = "",
    ) -> bool:
        """True if this rule applies to a file with the given metadata."""
        if not self.enabled or date is None:
            return False
        if not (self.start <= date <= self.end):
            return False
        if self.devices and device not in self.devices:
            return False
        if self.categories and category not in self.categories:
            return False
        return True


# ── helpers ───────────────────────────────────────────────────────────────────

def try_parse_datetime(value: str) -> Optional[datetime]:
    """Public, tolerant parser. Returns None on failure or empty input.

    Accepts:
        2025-04-01
        2025-04-01 14:30
        2025-04-01 14:30:00
        2025-04-01T14:30:00
        2025/04/01
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_dt(value: str, *, default: datetime) -> datetime:
    """Internal helper used during deserialisation — falls back to *default*."""
    parsed = try_parse_datetime(value)
    return parsed if parsed is not None else default


def load_rules(config: dict) -> list[EventRule]:
    return [EventRule.from_dict(d) for d in config.get("event_rules", [])]


def find_match(
    rules:   Iterable[EventRule],
    date:    Optional[datetime],
    device:  str = "",
    category: str = "",
) -> Optional[EventRule]:
    """Return the highest-priority enabled rule that matches, or None.

    On equal priority, ties are broken by *narrower* scope first (a rule with
    a device/category filter beats a wildcard one), then by name (stable).
    """
    matches = [r for r in rules if r.matches(date, device, category)]
    if not matches:
        return None

    def specificity(r: EventRule) -> tuple[int, int, int]:
        # higher priority wins; then more specific filters; then alphabetical name
        narrowness = bool(r.devices) + bool(r.categories)
        return (-r.priority, -narrowness, r.name.lower() == r.name)

    return min(matches, key=specificity)
