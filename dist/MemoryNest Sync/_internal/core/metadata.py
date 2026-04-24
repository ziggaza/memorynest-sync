"""
Extract date-taken and device info from photo/video files.

Priority order for date:
  1. EXIF DateTimeOriginal (photos)
  2. EXIF DateTime
  3. Video "Encoded date" / "Recorded date" (via pymediainfo)
  4. File modification time (fallback)

Priority order for device:
  1. EXIF Make + Model (photos)
  2. Video track "Encoded_Application" / "com.apple.quicktime.model" etc.
  3. None  (caller will use Unknown_Device)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import exifread
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

EXIF_DATE_TAGS = [
    "EXIF DateTimeOriginal",
    "EXIF DateTimeDigitized",
    "Image DateTime",
]
EXIF_DATE_FMT = "%Y:%m:%d %H:%M:%S"


@dataclass
class MediaMetadata:
    date: Optional[datetime] = None
    make: Optional[str] = None
    model: Optional[str] = None
    # raw key used for device_resolver lookup  e.g. "Panasonic|DC-GH6"
    device_key: Optional[str] = None
    date_source: str = "unknown"      # "exif" | "video_meta" | "file_mtime"
    error: Optional[str] = None


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_exif_date(raw: str) -> Optional[datetime]:
    try:
        return datetime.strptime(raw.strip(), EXIF_DATE_FMT)
    except (ValueError, AttributeError):
        return None


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def _clean(value: str) -> str:
    return value.strip().strip("\x00").strip()


# ── photo ─────────────────────────────────────────────────────────────────────

def _extract_photo(path: Path) -> MediaMetadata:
    meta = MediaMetadata()

    try:
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False, stop_tag="GPS GPSDate")
    except Exception as e:
        meta.error = f"exifread failed: {e}"
        tags = {}

    # date
    for tag in EXIF_DATE_TAGS:
        if tag in tags:
            dt = _parse_exif_date(str(tags[tag]))
            if dt:
                meta.date = dt
                meta.date_source = "exif"
                break

    # make / model
    make = _clean(str(tags["Image Make"])) if "Image Make" in tags else None
    model = _clean(str(tags["Image Model"])) if "Image Model" in tags else None

    # fallback: try Pillow for formats exifread may miss (HEIC, AVIF, WebP)
    if not make and not model and not meta.date:
        try:
            with Image.open(path) as img:
                exif_data = img.getexif() if hasattr(img, "getexif") else {}
                if exif_data:
                    # Pillow tag IDs: 271=Make, 272=Model, 306=DateTime, 36867=DateTimeOriginal
                    make = make or _clean(exif_data.get(271, "") or "")
                    model = model or _clean(exif_data.get(272, "") or "")
                    if not meta.date:
                        for tag_id in (36867, 36868, 306):
                            raw = exif_data.get(tag_id)
                            if raw:
                                dt = _parse_exif_date(str(raw))
                                if dt:
                                    meta.date = dt
                                    meta.date_source = "exif"
                                    break
        except (UnidentifiedImageError, Exception):
            pass

    meta.make = make or None
    meta.model = model or None
    if make and model:
        meta.device_key = f"{make}|{model}"

    if not meta.date:
        meta.date = _file_mtime(path)
        meta.date_source = "file_mtime"

    return meta


# ── video ─────────────────────────────────────────────────────────────────────

def _extract_video(path: Path) -> MediaMetadata:
    meta = MediaMetadata()

    try:
        from pymediainfo import MediaInfo
        info = MediaInfo.parse(path)
    except Exception as e:
        meta.error = f"pymediainfo failed: {e}"
        meta.date = _file_mtime(path)
        meta.date_source = "file_mtime"
        return meta

    general = next((t for t in info.tracks if t.track_type == "General"), None)
    if not general:
        meta.date = _file_mtime(path)
        meta.date_source = "file_mtime"
        return meta

    # date: try multiple mediainfo fields
    date_fields = [
        "recorded_date",
        "encoded_date",
        "tagged_date",
        "file_last_modification_date",
    ]
    for field_name in date_fields:
        raw = getattr(general, field_name, None)
        if raw:
            raw = str(raw).strip()
            # mediainfo formats: "UTC 2024-06-15 10:30:00" or "2024-06-15T10:30:00+07:00"
            for fmt in (
                "UTC %Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
            ):
                try:
                    dt = datetime.strptime(raw[:19].replace("T", " "), fmt[:len(fmt)])
                    # strip tz prefix "UTC " if present
                    candidate = raw.replace("UTC ", "")
                    dt = datetime.strptime(candidate[:19].replace("T", " "),
                                           "%Y-%m-%d %H:%M:%S")
                    meta.date = dt
                    meta.date_source = "video_meta"
                    break
                except ValueError:
                    continue
        if meta.date:
            break

    # device: check QuickTime / XMP tags embedded in General track
    make_fields = ["comapplequicktimemake", "make", "producer"]
    model_fields = ["comapplequicktimemodel", "model"]

    make = None
    model = None
    for f in make_fields:
        v = getattr(general, f, None)
        if v:
            make = _clean(str(v))
            break
    for f in model_fields:
        v = getattr(general, f, None)
        if v:
            model = _clean(str(v))
            break

    meta.make = make or None
    meta.model = model or None
    if make and model:
        meta.device_key = f"{make}|{model}"
    elif model:
        meta.device_key = f"|{model}"

    if not meta.date:
        meta.date = _file_mtime(path)
        meta.date_source = "file_mtime"

    return meta


# ── public API ────────────────────────────────────────────────────────────────

def extract(path: Path, media_type: str) -> MediaMetadata:
    """
    media_type: "photo" or "video" (case-insensitive).
    Returns MediaMetadata. Never raises.
    """
    try:
        if media_type.lower() != "video":
            return _extract_photo(path)
        else:
            return _extract_video(path)
    except Exception as e:
        logger.exception("Unexpected error extracting metadata from %s", path)
        m = MediaMetadata(error=str(e))
        m.date = _file_mtime(path)
        m.date_source = "file_mtime"
        return m
