"""
Infer device name from filename patterns when EXIF/video metadata has no device info.

This is a best-effort heuristic — used only when metadata extraction returns no Make/Model.
Patterns are ordered from most-specific to least-specific.

Returns None if no pattern matches (caller will use Unknown_Device).
"""

import re
from pathlib import Path
from typing import Optional

# Each entry: (compiled_regex, device_name)
# Matched against the filename stem (without extension), case-insensitive.
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # DJI drones / action cameras
    (re.compile(r"^DJI_\d+$",         re.IGNORECASE), "DJI Drone"),
    (re.compile(r"^DJI_\d{4}[A-Z]",   re.IGNORECASE), "DJI Drone"),
    (re.compile(r"^GOPR\d+",           re.IGNORECASE), "GoPro"),
    (re.compile(r"^GP\d{6}",           re.IGNORECASE), "GoPro"),
    (re.compile(r"^S\d{7}",            re.IGNORECASE), "GoPro"),          # GoPro S0xxxxxx
    (re.compile(r"^G\d{7}",            re.IGNORECASE), "GoPro"),

    # Panasonic Lumix — video naming: C0001.MP4, P2XXXXXX.JPG
    (re.compile(r"^C\d{4}$",           re.IGNORECASE), "Panasonic Lumix"),
    (re.compile(r"^P\d{7}$",           re.IGNORECASE), "Panasonic Lumix"),

    # Sony AVCHD / Handycam naming: 00001.MTS, 000001.MTS
    (re.compile(r"^\d{5}$"),                            "Sony AVCHD"),
    (re.compile(r"^\d{6}$"),                            "Sony AVCHD"),

    # Sony Alpha: A7I07804, DSC02383, DSC07884
    (re.compile(r"^A7[RMSCI]?\d{5}",  re.IGNORECASE), "Sony A7 Series"),
    (re.compile(r"^DSC\d{5}",         re.IGNORECASE), "Sony Camera"),

    # Samsung / Android generic: 20230730_170149
    (re.compile(r"^\d{8}_\d{6}$"),                     "Android Camera"),

    # iPhone / iOS: IMG_3698, IMG_E3698 (edited), VID_3698
    (re.compile(r"^IMG_E?\d{4}$",     re.IGNORECASE), "iPhone"),
    (re.compile(r"^VID_\d{4}$",       re.IGNORECASE), "iPhone"),

    # WhatsApp / social downloads
    (re.compile(r"^IMG-\d{8}-WA\d+",  re.IGNORECASE), "WhatsApp"),
    (re.compile(r"^VID-\d{8}-WA\d+",  re.IGNORECASE), "WhatsApp"),
    (re.compile(r"^FB_IMG_\d{13}",    re.IGNORECASE), "Facebook"),

    # Parrot drones
    (re.compile(r"^Jumping_Race_",     re.IGNORECASE), "Parrot Jumping Race"),
    (re.compile(r"^Bebop_",            re.IGNORECASE), "Parrot Bebop"),

    # Screenshot patterns
    (re.compile(r"^Screenshot_\d{8}", re.IGNORECASE), "Screenshot"),
    (re.compile(r"^screenshot",        re.IGNORECASE), "Screenshot"),
]


def guess_device(path: Path) -> Optional[str]:
    """
    Return a device name inferred from the filename, or None if no pattern matches.
    Used only when metadata extraction finds no Make/Model.
    """
    stem = path.stem
    for pattern, device in _PATTERNS:
        if pattern.match(stem):
            return device
    return None
