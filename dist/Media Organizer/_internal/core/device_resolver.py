"""
Map EXIF (Make|Model) keys → user-friendly marketing names.

Lookup order:
  1. Exact match on "Make|Model" key in config device_mappings
  2. Case-insensitive match
  3. Model-only partial match (strips Make prefix)
  4. Return the raw EXIF string as-is, and record it as unresolved
     so the GUI can prompt the user to add a proper mapping later.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DeviceResolver:
    def __init__(self, config: dict) -> None:
        raw: dict = config.get("device_mappings", {})
        # build two lookup tables: exact and lowercase
        self._exact: dict[str, str] = raw
        self._lower: dict[str, str] = {k.lower(): v for k, v in raw.items()}
        self._unknown_folder: str = config.get("settings", {}).get(
            "unknown_device_folder", "Unknown_Device"
        )
        # tracks device keys seen but not in mapping  {device_key: raw_label}
        self._unresolved: dict[str, str] = {}

    # ── public ────────────────────────────────────────────────────────────────

    def resolve(self, make: Optional[str], model: Optional[str]) -> str:
        """
        Return marketing name or fall back gracefully.
        Never raises.
        """
        if not make and not model:
            return self._unknown_folder

        key = self._build_key(make, model)

        # 1. exact match
        if key in self._exact:
            return self._exact[key]

        # 2. case-insensitive
        if key.lower() in self._lower:
            return self._lower[key.lower()]

        # 3. model-only (some cameras omit Make or repeat brand in Model)
        if model:
            model_key = f"|{model}"
            if model_key.lower() in self._lower:
                return self._lower[model_key.lower()]
            # partial: check if any mapping value starts with model
            for k, v in self._lower.items():
                if k.endswith(f"|{model.lower()}"):
                    return v

        # 4. unresolved — use sanitised raw string, track for later
        raw_label = self._sanitise(f"{make} {model}".strip() if make else model or "")
        self._unresolved[key] = raw_label
        logger.info("Unresolved device: %s → using raw label '%s'", key, raw_label)
        return raw_label

    @property
    def unresolved_devices(self) -> dict[str, str]:
        """Returns {device_key: raw_folder_name} for all unseen devices."""
        return dict(self._unresolved)

    def add_mapping(self, device_key: str, marketing_name: str) -> None:
        """Dynamically add a mapping (called from Device Manager UI)."""
        self._exact[device_key] = marketing_name
        self._lower[device_key.lower()] = marketing_name
        self._unresolved.pop(device_key, None)

    # ── private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_key(make: Optional[str], model: Optional[str]) -> str:
        return f"{make or ''}|{model or ''}"

    @staticmethod
    def _sanitise(name: str) -> str:
        """Make a string safe to use as a folder name."""
        bad = r'\/:*?"<>|'
        for ch in bad:
            name = name.replace(ch, "_")
        return name.strip("._") or "Unknown_Device"
