# MemoryNest Sync — User Guide

**A safe haven for your precious memories.** MemoryNest Sync is a smart, family-friendly desktop application that gently organizes your scattered photos and videos from multiple drives into a beautiful, structured digital diary.

Instead of worrying about messy files or full hard drives, let MemoryNest Sync do the heavy lifting. It safely gathers your memories into a neat folder hierarchy, smartly detects duplicates to save space, and features a calming GUI. You can easily pause and resume the syncing process at any time.

> Developed by **ZigGaZa Studio**

---

## Table of Contents

1. [Requirements](#requirements)
2. [How to Run](#how-to-run)
3. [Quick Start](#quick-start)
4. [Main Window](#main-window)
5. [Options Explained](#options-explained)
6. [Device Manager](#device-manager)
7. [Folder Structure Manager](#folder-structure-manager)
8. [Category Manager](#category-manager)
9. [Output Folder Structure](#output-folder-structure)
10. [Duplicate Handling](#duplicate-handling)
11. [Resume / Checkpoint](#resume--checkpoint)
12. [Logs](#logs)
13. [Tips for Large Libraries (20TB+)](#tips-for-large-libraries-20tb)

---

## Requirements

| Item | Minimum |
|------|---------|
| OS | Windows 10 / 11 (64-bit) |
| Python | 3.10 or newer |
| Libraries | See `requirements.txt` |

Install dependencies once:
```
pip install -r requirements.txt
```

---

## How to Run

**Double-click:**
```
Run MemoryNest Sync.bat
```
The launcher uses `pythonw.exe` — no console window will open.

**Or from terminal:**
```
python main.py
```

### System Tray
When you close the window (X button), the app **minimizes to the system tray** — it does not quit.
- **Right-click the tray icon** → Show / Quit
- **Double-click the tray icon** → Restore window

---

## Quick Start

1. Click **+ Add Folder** to add one or more source folders (can be different drives)
2. Click **Browse** to choose a destination folder
3. Check **Dry Run** is ON (default) — no files will be touched
4. Click **▶ Start**
5. Review the Activity Log to verify paths look correct
6. Uncheck **Dry Run**, click **▶ Start** again to move/copy for real

---

## Main Window

```
┌─────────────────────────────────────────────────────────────┐
│  MemoryNest Sync                          🌙  Dark           │
├──────────────────────┬──────────────────────────────────────┤
│  Source Folders      │  370  338  32   0    0    0          │
│  [+ Add] [Remove]    │  Tot  Pho  Vid  Dup  Res  Err        │
│                      │──────────────────────────────────────│
│  Destination Folder  │  Activity Log                        │
│  [path] [Browse]     │  [MOV] IMG_001.JPG => Photos/...     │
│                      │  [DUP] DSC_002.JPG (duplicate)       │
│  Options             │  ...                                  │
│  ☑ Dry Run           │──────────────────────────────────────│
│  ☑ Detect duplicates │  Overall ████████░░  338 / 370       │
│  ☑ Include sub-dirs  │  Current ████░░░░░░  IMG_001.JPG     │
│  ☑ Resume            │                                       │
│  Operation: ○Copy ●Move                                     │
│  Metadata threads: 4                                        │
│                      │                                       │
│  [Device Manager]  [Folder Structure]                       │
│  [Category Manager]                                         │
│  [▶ Start]  [⏹ Stop]                                        │
└──────────────────────┴──────────────────────────────────────┘
```

### Theme Toggle (top-right)
Click the 🌙 / ☀️ / 🖥 button to cycle between **Dark → Light → System** mode.
Your preference is saved automatically.

### Stat Boxes
| Box | Meaning |
|-----|---------|
| Total | All media files found in source folders |
| Photos | Files processed as photos |
| Videos | Files processed as videos |
| Dupes | Duplicate files detected and quarantined |
| Resumed | Files skipped because already processed in a previous run |
| Errors | Files that could not be read or moved |

---

## Options Explained

### Dry Run
When checked, the app **simulates** the operation without touching any files.
- Activity Log shows `[DRY]` for each file
- Use this to verify the output structure before committing

### Detect & Quarantine Duplicates
Detects exact-copy duplicates using fast xxHash fingerprinting.
- Duplicates are moved/copied to a `Duplicates/` subfolder in the destination
- The first copy encountered is kept in its correct folder

### Include Sub-folders
When checked, scans all sub-folders inside each source folder recursively.

### Resume
Skips files that were already successfully processed in a previous run.
- Uses a SQLite checkpoint database stored in `<destination>/.organizer/progress.db`
- Safe to interrupt and restart — no files will be double-processed

### Operation: Copy / Move
- **Copy** — source files are kept; copies are placed in the destination
- **Move** — source files are removed after being placed in the destination
- A confirmation dialog appears when Dry Run is OFF

### Metadata Threads
Number of parallel threads for reading EXIF/video metadata.
- Higher = faster scanning
- Recommended: **4** for HDD, **6–8** for SSD

---

## Device Manager

Opens a dialog to manage how camera make/model tags (from EXIF) are mapped to folder names.

**EXIF Key format:** `Make|Model` (e.g. `Panasonic|DMC-GX85`)
**Folder Name:** what appears in the folder path (e.g. `Panasonic GX85`)

### Auto-detected devices
When a file contains an EXIF device tag not in the mapping list, the app automatically adds it with the raw EXIF string as a temporary folder name. The **Device Manager** button shows a badge `(N)` in amber indicating how many devices need a proper name.

1. Open Device Manager
2. Find rows labeled **auto** (shown in amber)
3. Edit the Folder Name to a clean, readable name
4. Click **Save**

---

## Folder Structure Manager

Controls how the destination folder hierarchy is built.

### Available Segments

| Segment | Example output | Format options |
|---------|---------------|----------------|
| Category | `Photos` / `Videos` | — |
| Device | `Panasonic GX85` | — |
| Year | `2024` | — |
| Quarter | `Q2` | — (always Q1–Q4) |
| Month | `06_June` | `MM_MonthName` / `MM` / `MonthName` |
| Year-Month | `2024-06` | `YYYY-MM` / `YYYYMM` / `YYYY_MM` |
| Day | `20240615` | `YYYYMMDD` / `DD` / `YYYY-MM-DD` |

Each segment can be:
- **Enabled/disabled** via checkbox
- **Reordered** with ↑ ↓ buttons

**Quarter grouping** (Q1 = Jan–Mar, Q2 = Apr–Jun, Q3 = Jul–Sep, Q4 = Oct–Dec) is useful for reviewing memories every 3 months.

### Presets

| Preset | Structure |
|--------|-----------|
| Default | `Category / Device / Year / Month` |
| With Day | `Category / Device / Year / Month / Day` |
| Date-first | `Year / Month / Device / Category` |
| Flat | `Category / Device / Year` |

A **live preview** updates as you make changes.

---

## Category Manager

Manages which file extensions belong to which category (Photos, Videos, or custom).

### Built-in Categories
- **Photos** — JPEG, HEIC, PNG, RAW formats (CR3, ARW, NEF, etc.)
- **Videos** — MP4, MOV, MTS, MXF, BRAW, etc.

These cannot be deleted but extensions can be edited freely.

### Adding a Custom Category
1. Click **+ New Category**
2. Set a **Category Name** (shown in folder path)
3. Set a **Folder Name** (actual folder created on disk)
4. Choose **Metadata type**: Photo (EXIF) or Video
5. Add extensions using the text field
6. Click **Save**

**Example:** Create a "RAW Files" category with `.arw .cr3 .nef` extensions and its own folder.

---

## Output Folder Structure

Default structure (example):
```
Destination/
├── Photos/
│   ├── iPhone 15 Pro/
│   │   └── 2024/
│   │       └── 06_June/
│   │           └── 20240615/
│   │               └── IMG_0001.HEIC
│   └── Panasonic GX85/
│       └── 2024/
│           └── 11_November/
│               └── 20241101/
│                   └── P1010001.RW2
├── Videos/
│   └── DJI Mini 3 Pro/
│       └── 2024/
│           └── 06_June/
│               └── DJI_0001.MP4
├── Duplicates/
│   └── IMG_0001_1.HEIC
└── .organizer/          ← internal database, do not delete
    ├── hashes.db
    └── progress.db
```

### Unknown Device
If no device info can be determined (no EXIF, no filename pattern match), the file goes into:
```
Photos/Unknown_Device/2024/06_June/
```

### Conflict Resolution
If a filename already exists at the destination, the app appends `_1`, `_2`, etc.:
```
IMG_0001.JPG → IMG_0001_1.JPG → IMG_0001_2.JPG
```

---

## Duplicate Handling

The app uses xxHash to fingerprint every file's content.

1. First time a file is seen → fingerprint stored, file moved/copied normally
2. Same file encountered again → detected as duplicate, moved to `Duplicates/` folder
3. The duplicate's original location is logged

Duplicates are **not deleted** — they are quarantined so you can review them.

---

## Resume / Checkpoint

The checkpoint database (`progress.db`) records every file's processing status.

| Status | Meaning |
|--------|---------|
| moved | File was moved successfully |
| copied | File was copied successfully |
| duplicate | File was a duplicate, sent to Duplicates/ |
| skipped | File extension not recognized |
| error | Processing failed (see log for details) |

On the next run with **Resume** checked, files with status `moved`, `copied`, or `duplicate` are skipped.

**To start fresh:** uncheck **Resume** or delete `<destination>/.organizer/progress.db`.

---

## Logs

Application logs are saved to:
```
<app folder>/logs/organizer_YYYY-MM-DD.log
```

Logs rotate daily and contain detailed per-file records useful for auditing.

---

## Tips for Large Libraries (20TB+)

1. **Always do a Dry Run first** on a small sample folder before processing 20TB
2. **Process one drive at a time** — add one source folder, run, then add the next
3. **Use Move, not Copy** when disk space is tight (Copy needs 2× the space temporarily)
4. **Use Resume** — you can safely pause and restart at any time
5. **SSD destination** is strongly recommended for performance
6. **Set threads to 4–6** for HDD sources; up to 8 for SSD sources
7. **Do not rename or move the `.organizer` folder** — it is required for resume and deduplication to work across sessions
8. **Check Errors count** after each run — files with errors are skipped, not lost

---

<div align="center">

**POWERED BY ZigGaZa STUDIO**

*MemoryNest Sync — A safe haven for your precious memories.*

</div>
