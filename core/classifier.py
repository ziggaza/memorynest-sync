"""
Classify files by category based on extension.
Categories are loaded from config["categories"] — fully user-configurable.
Returns the category NAME string (e.g. "Photos", "Videos") or UNKNOWN.
"""

from pathlib import Path

UNKNOWN = "UNKNOWN"

# Cache: (config id) → {ext: category_name}
_cache: dict[int, dict[str, str]] = {}


def _build_map(config: dict) -> dict[str, str]:
    ext_map: dict[str, str] = {}
    for cat in config.get("categories", []):
        name = cat.get("name", "")
        for ext in cat.get("extensions", []):
            ext_lower = ext.lower()
            if ext_lower not in ext_map:   # first category wins on conflict
                ext_map[ext_lower] = name
    return ext_map


def classify(path: Path, config: dict) -> str:
    key = id(config)
    if key not in _cache:
        _cache.clear()            # keep only one config cached at a time
        _cache[key] = _build_map(config)
    ext_map = _cache[key]
    return ext_map.get(path.suffix.lower(), UNKNOWN)


def is_media(path: Path, config: dict) -> bool:
    return classify(path, config) != UNKNOWN
