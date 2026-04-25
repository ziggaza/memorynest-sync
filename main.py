"""
Media Organizer — Main GUI
Improvements: theme toggle, move/copy, device-manager auto-populate, folder-structure manager.
"""

import json
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.log_setup import setup as log_setup
from core.mover import Organizer, OrganizerEvent, EventKind
from core.path_builder import PathBuilder, DEFAULT_SEGMENTS, MONTH_NAMES
from core.sound import SoundEngine, THEMES as SOUND_THEMES

APP_VERSION  = "1.0.0"

# ── paths ──────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
CONFIG_PATH  = BASE_DIR / "config.json"
SETTINGS_PATH= BASE_DIR / "settings.json"
LOG_DIR      = BASE_DIR / "logs"

log_setup(LOG_DIR)

# ── Windows taskbar icon fix ───────────────────────────────────────────────────
try:
    import ctypes as _ctypes
    _ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "ZigGaZa.MemoryNestSync.1"
    )
except Exception:
    pass

# ── settings helpers ───────────────────────────────────────────────────────────
_DEFAULT_SETTINGS = {
    "theme":          "dark",
    "operation":      "copy",
    # sound system (added v1.1)
    "sound_enabled":  False,         # off by default — opt-in
    "sound_theme":    "nature",      # "nature" | "minimal" | "none"
    "sound_volume":   0.6,           # 0.0 – 1.0
    # notifications (added v1.1)
    "notify_on_done": True,
}

def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            return {**_DEFAULT_SETTINGS,
                    **json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return dict(_DEFAULT_SETTINGS)

def save_settings(s: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(s, indent=2), encoding="utf-8")

def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _tc() -> dict:
    """Return theme-aware colors for native tk widgets (Listbox, Text)."""
    dark = ctk.get_appearance_mode().lower() == "dark"
    return {
        "lb_bg":  "#2D2318" if dark else "#EDE5D5",
        "lb_fg":  "#F0E0C0" if dark else "#2D1C08",
        "lb_sel": "#C8882A",
        "log_bg": "#1E1710" if dark else "#EDE5D5",
        "log_fg": "#E8D5B0" if dark else "#2D1C08",
    }


def _apply_icon(window: ctk.CTkToplevel) -> None:
    """Set the app icon on a CTkToplevel.
    CTkToplevel calls _windows_set_titlebar_icon() via after(200, ...) which
    resets the icon — we must fire AFTER that, so 300 ms is the safe minimum.
    """
    ico = str(BASE_DIR / "assets" / "icon.ico")
    if not (BASE_DIR / "assets" / "icon.ico").exists():
        return
    def _set():
        try:
            window.iconbitmap(ico)
        except Exception:
            pass
    window.after(300, _set)


# ── Device Manager dialog ──────────────────────────────────────────────────────

class DeviceManagerDialog(ctk.CTkToplevel):
    def __init__(self, parent, config: dict, on_save):
        super().__init__(parent)
        self.title("Device Manager")
        self.geometry("820x560")
        self.resizable(True, True)
        _apply_icon(self)
        self._config  = config
        self._on_save = on_save
        # rows: (key_entry, val_entry, is_auto_label)
        self._rows: list[tuple[ctk.CTkEntry, ctk.CTkEntry]] = []
        self._build()
        self.grab_set()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=16, pady=(12, 0), sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr, text="EXIF Key  (Make|Model)",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     width=300, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="Folder Name",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     anchor="w").grid(row=0, column=1, sticky="w", padx=(8, 0))
        ctk.CTkLabel(hdr, text="Source",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     width=80, anchor="w").grid(row=0, column=2, sticky="w", padx=(8, 0))

        # note
        auto_keys = set(self._config.get("auto_detected_keys", []))
        if auto_keys:
            ctk.CTkLabel(self,
                         text=f"  {len(auto_keys)} auto-detected device(s) need a folder name  (shown in amber)",
                         text_color="#C8882A",
                         font=ctk.CTkFont(size=11)
                         ).grid(row=0, column=0, padx=16, pady=(0, 2), sticky="e")

        # scrollable body
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=1, column=0, padx=16, pady=4, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)
        self._scroll.grid_columnconfigure(1, weight=1)

        mappings = self._config.get("device_mappings", {})
        for i, (key, val) in enumerate(mappings.items()):
            self._add_row(key, val, i, is_auto=(key in auto_keys))

        # buttons
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")
        ctk.CTkButton(bar, text="+ Add Row", width=110,
                      command=self._add_empty_row).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bar, text="Save", width=110,
                      command=self._save).pack(side="right")
        ctk.CTkButton(bar, text="Cancel", width=110,
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self.destroy).pack(side="right", padx=(0, 8))

    def _add_row(self, key="", val="", row=None, is_auto=False):
        if row is None:
            row = len(self._rows)
        fg = "#C8882A" if is_auto else ctk.ThemeManager.theme["CTkEntry"]["border_color"][1]

        k_entry = ctk.CTkEntry(self._scroll, placeholder_text="Make|Model",
                               border_color=fg if is_auto else None)
        k_entry.grid(row=row, column=0, padx=(0, 6), pady=3, sticky="ew")
        k_entry.insert(0, key)

        v_entry = ctk.CTkEntry(self._scroll, placeholder_text="Folder Name",
                               border_color=fg if is_auto else None)
        v_entry.grid(row=row, column=1, padx=(0, 6), pady=3, sticky="ew")
        v_entry.insert(0, val)

        src_lbl = ctk.CTkLabel(self._scroll,
                               text="auto" if is_auto else "defined",
                               text_color="#C8882A" if is_auto else ("gray50", "#9A8060"),
                               font=ctk.CTkFont(size=10), width=60, anchor="w")
        src_lbl.grid(row=row, column=2, pady=3, sticky="w")

        self._rows.append((k_entry, v_entry))

    def _add_empty_row(self):
        self._add_row()

    def _save(self):
        new_mappings, saved_keys = {}, set()
        for k_e, v_e in self._rows:
            k, v = k_e.get().strip(), v_e.get().strip()
            if k and v:
                new_mappings[k] = v
                saved_keys.add(k)
        # remove auto_detected_keys that now have a proper name
        auto_keys = set(self._config.get("auto_detected_keys", []))
        remaining_auto = [k for k in auto_keys if k in saved_keys and
                          new_mappings.get(k) == k]   # still has raw key as value
        self._config["device_mappings"]   = new_mappings
        self._config["auto_detected_keys"] = remaining_auto
        save_config(self._config)
        self._on_save(self._config)
        self.destroy()


# ── Folder Structure Manager dialog ───────────────────────────────────────────

SEGMENT_META = {
    "category":   {"label": "Category",   "desc": "Photos / Videos",       "fmt_opts": None},
    "device":     {"label": "Device",     "desc": "from EXIF / filename",   "fmt_opts": None},
    "year":       {"label": "Year",       "desc": "YYYY",                   "fmt_opts": None},
    "quarter":    {"label": "Quarter",    "desc": "Q1 / Q2 / Q3 / Q4",     "fmt_opts": None},
    "month":      {"label": "Month",      "desc": "",
                   "fmt_opts": ["MM_MonthName", "MM", "MonthName"]},
    "year_month": {"label": "Year-Month", "desc": "",
                   "fmt_opts": ["YYYY-MM", "YYYYMM", "YYYY_MM"]},
    "day":        {"label": "Day",        "desc": "",
                   "fmt_opts": ["YYYYMMDD", "DD", "YYYY-MM-DD"]},
}

PRESETS = {
    "Default":      {"segments": ["category","device","year","month"],      "month_format":"MM_MonthName","day_format":"YYYYMMDD"},
    "With Day":     {"segments": ["category","device","year","month","day"],"month_format":"MM_MonthName","day_format":"YYYYMMDD"},
    "Date-first":   {"segments": ["year","month","device","category"],      "month_format":"MM_MonthName","day_format":"YYYYMMDD"},
    "Flat":         {"segments": ["category","device","year"],              "month_format":"MM_MonthName","day_format":"YYYYMMDD"},
}


class FolderStructureDialog(ctk.CTkToplevel):
    def __init__(self, parent, config: dict, on_save):
        super().__init__(parent)
        self.title("Folder Structure Manager")
        self.geometry("620x610")
        _apply_icon(self)
        self.resizable(False, False)
        self._config   = config
        self._on_save  = on_save

        fs = config.get("folder_structure", {})
        active = fs.get("segments", list(DEFAULT_SEGMENTS))
        # build full ordered list: active first, then remaining
        all_keys = list(SEGMENT_META.keys())
        inactive = [k for k in all_keys if k not in active]
        self._order: list[str]  = list(active) + inactive
        self._enabled: dict[str, tk.BooleanVar] = {
            k: tk.BooleanVar(value=(k in active)) for k in all_keys
        }
        self._fmt: dict[str, tk.StringVar] = {
            "month":      tk.StringVar(value=fs.get("month_format",      "MM_MonthName")),
            "year_month": tk.StringVar(value=fs.get("year_month_format", "YYYY-MM")),
            "day":        tk.StringVar(value=fs.get("day_format",        "YYYYMMDD")),
        }
        self._row_frames: list[ctk.CTkFrame] = []
        self._build()
        self.grab_set()

    # ── build ──────────────────────────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Drag  ↑ ↓  to reorder segments",
                     font=ctk.CTkFont(size=11), text_color="gray60"
                     ).grid(row=0, column=0, padx=16, pady=(10,2), sticky="w")

        self._list_frame = ctk.CTkScrollableFrame(self, height=320)
        self._list_frame.grid(row=1, column=0, padx=16, pady=(0,4), sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)
        self._render_rows()

        # ── preview ──
        prev_outer = ctk.CTkFrame(self)
        prev_outer.grid(row=2, column=0, padx=16, pady=(0,8), sticky="ew")
        prev_outer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(prev_outer, text="Preview",
                     font=ctk.CTkFont(size=11, weight="bold")
                     ).grid(row=0, column=0, padx=10, pady=(8,2), sticky="w")
        self._preview_var = tk.StringVar()
        ctk.CTkLabel(prev_outer, textvariable=self._preview_var,
                     font=ctk.CTkFont(family="Consolas", size=11),
                     text_color="#E0A030", anchor="w"
                     ).grid(row=1, column=0, padx=10, pady=(0,8), sticky="ew")
        self._update_preview()

        # ── presets ──
        preset_frame = ctk.CTkFrame(self, fg_color="transparent")
        preset_frame.grid(row=3, column=0, padx=16, pady=(0,4), sticky="ew")
        ctk.CTkLabel(preset_frame, text="Presets:",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,8))
        for name in PRESETS:
            ctk.CTkButton(preset_frame, text=name, width=90, height=26,
                          fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                          command=lambda n=name: self._apply_preset(n)
                          ).pack(side="left", padx=(0,4))

        # ── save / cancel ──
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.grid(row=4, column=0, padx=16, pady=(0,12), sticky="ew")
        ctk.CTkButton(btn_bar, text="Save", width=110,
                      command=self._save).pack(side="right")
        ctk.CTkButton(btn_bar, text="Cancel", width=110,
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self.destroy).pack(side="right", padx=(0,8))

    # ── row rendering ──────────────────────────────────────────────────────────
    def _render_rows(self):
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._row_frames.clear()

        for i, key in enumerate(self._order):
            meta = SEGMENT_META[key]
            row_f = ctk.CTkFrame(self._list_frame, fg_color=("#DDD0BE", "#2D2318"), corner_radius=6)
            row_f.grid(row=i, column=0, pady=3, sticky="ew")
            row_f.grid_columnconfigure(2, weight=1)

            # up / down
            ctk.CTkButton(row_f, text="↑", width=28, height=28,
                          fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                          command=lambda k=key: self._move(k, -1)
                          ).grid(row=0, column=0, padx=(6,2), pady=6)
            ctk.CTkButton(row_f, text="↓", width=28, height=28,
                          fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                          command=lambda k=key: self._move(k, +1)
                          ).grid(row=0, column=1, padx=(0,8), pady=6)

            # checkbox
            ctk.CTkCheckBox(row_f, text="", variable=self._enabled[key],
                            width=20, command=self._update_preview
                            ).grid(row=0, column=2, padx=(0,4))

            # label + desc
            ctk.CTkLabel(row_f, text=meta["label"],
                         font=ctk.CTkFont(size=12, weight="bold"), width=70, anchor="w"
                         ).grid(row=0, column=3, padx=(0,4))

            if meta["fmt_opts"]:
                fmt_key = key
                ctk.CTkOptionMenu(row_f, variable=self._fmt[fmt_key],
                                  values=meta["fmt_opts"], width=130,
                                  command=lambda _v, _k=fmt_key: self._update_preview()
                                  ).grid(row=0, column=4, padx=(0,10))
            else:
                ctk.CTkLabel(row_f, text=meta["desc"],
                             font=ctk.CTkFont(size=11), text_color="gray60"
                             ).grid(row=0, column=4, padx=(0,10))

            self._row_frames.append(row_f)

    def _move(self, key: str, direction: int):
        idx = self._order.index(key)
        new_idx = idx + direction
        if 0 <= new_idx < len(self._order):
            self._order[idx], self._order[new_idx] = self._order[new_idx], self._order[idx]
            self._render_rows()
            self._update_preview()

    def _apply_preset(self, name: str):
        p = PRESETS[name]
        self._order = list(p["segments"]) + [k for k in SEGMENT_META if k not in p["segments"]]
        for k, var in self._enabled.items():
            var.set(k in p["segments"])
        self._fmt["month"].set(p.get("month_format", "MM_MonthName"))
        self._fmt["year_month"].set(p.get("year_month_format", "YYYY-MM"))
        self._fmt["day"].set(p.get("day_format", "YYYYMMDD"))
        self._render_rows()
        self._update_preview()

    def _update_preview(self, *_):
        segments = [k for k in self._order if self._enabled[k].get()]
        tmp_cfg = {
            **self._config,
            "folder_structure": {
                "segments":          segments,
                "month_format":      self._fmt["month"].get(),
                "year_month_format": self._fmt["year_month"].get(),
                "day_format":        self._fmt["day"].get(),
            }
        }
        pb = PathBuilder(tmp_cfg)
        text = pb.preview()
        self._preview_var.set(text)

    def _save(self):
        segments = [k for k in self._order if self._enabled[k].get()]
        if not segments:
            messagebox.showwarning("Empty Structure",
                                   "At least one segment must be enabled.", parent=self)
            return
        self._config["folder_structure"] = {
            "segments":          segments,
            "month_format":      self._fmt["month"].get(),
            "year_month_format": self._fmt["year_month"].get(),
            "day_format":        self._fmt["day"].get(),
        }
        save_config(self._config)
        self._on_save(self._config)
        self.destroy()


# ── Category Manager dialog ────────────────────────────────────────────────────

class CategoryManagerDialog(ctk.CTkToplevel):
    def __init__(self, parent, config: dict, on_save):
        super().__init__(parent)
        self.title("Category Manager")
        self.geometry("780x540")
        _apply_icon(self)
        self.resizable(True, True)
        self._config  = config
        self._on_save = on_save

        import copy
        self._cats: list[dict] = copy.deepcopy(config.get("categories", []))
        self._sel_idx = 0

        self._build()
        self.grab_set()
        if self._cats:
            self._select(0)

    # ── build ──────────────────────────────────────────────────────────────────
    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ─ left: category list ─
        left = ctk.CTkFrame(self, width=210)
        left.grid(row=0, column=0, padx=(12,0), pady=12, sticky="nsew")
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left, text="Categories",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, padx=10, pady=(10,4), sticky="w")

        self._cat_list = tk.Listbox(
            left, bg=_tc()["lb_bg"], fg=_tc()["lb_fg"], selectbackground=_tc()["lb_sel"],
            relief="flat", font=("Segoe UI", 10), borderwidth=0,
            highlightthickness=0, activestyle="none")
        self._cat_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,4))
        self._cat_list.bind("<<ListboxSelect>>", self._on_list_select)

        ctk.CTkButton(left, text="+ New Category", height=30,
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self._add_category
                      ).grid(row=2, column=0, padx=8, pady=(0,10), sticky="ew")

        # ─ right: edit panel ─
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, padx=12, pady=12, sticky="nsew")
        right.grid_columnconfigure((0,1), weight=1)
        right.grid_rowconfigure(4, weight=1)

        # Name / Folder row
        ctk.CTkLabel(right, text="Category Name",
                     font=ctk.CTkFont(size=11)
                     ).grid(row=0, column=0, padx=(12,4), pady=(12,2), sticky="w")
        ctk.CTkLabel(right, text="Folder Name",
                     font=ctk.CTkFont(size=11)
                     ).grid(row=0, column=1, padx=(4,12), pady=(12,2), sticky="w")

        self._name_var   = tk.StringVar()
        self._folder_var = tk.StringVar()
        self._name_entry = ctk.CTkEntry(right, textvariable=self._name_var)
        self._name_entry.grid(row=1, column=0, padx=(12,4), pady=(0,6), sticky="ew")
        self._folder_entry = ctk.CTkEntry(right, textvariable=self._folder_var)
        self._folder_entry.grid(row=1, column=1, padx=(4,12), pady=(0,6), sticky="ew")

        # Type hint row
        hint_row = ctk.CTkFrame(right, fg_color="transparent")
        hint_row.grid(row=2, column=0, columnspan=2, padx=12, pady=(0,8), sticky="w")
        ctk.CTkLabel(hint_row, text="Metadata type:",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,10))
        self._hint_var = tk.StringVar(value="photo")
        ctk.CTkRadioButton(hint_row, text="Photo (EXIF)", variable=self._hint_var,
                           value="photo").pack(side="left", padx=(0,12))
        ctk.CTkRadioButton(hint_row, text="Video", variable=self._hint_var,
                           value="video").pack(side="left")

        # Extensions header
        ext_hdr = ctk.CTkFrame(right, fg_color="transparent")
        ext_hdr.grid(row=3, column=0, columnspan=2, padx=12, sticky="ew")
        ctk.CTkLabel(ext_hdr, text="Extensions",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        self._ext_count_lbl = ctk.CTkLabel(ext_hdr, text="",
                                            font=ctk.CTkFont(size=10),
                                            text_color="gray60")
        self._ext_count_lbl.pack(side="left", padx=(6,0))

        # Extensions listbox
        ext_frame = ctk.CTkFrame(right)
        ext_frame.grid(row=4, column=0, columnspan=2, padx=12, pady=(4,0), sticky="nsew")
        ext_frame.grid_columnconfigure(0, weight=1)
        ext_frame.grid_rowconfigure(0, weight=1)

        self._ext_listbox = tk.Listbox(
            ext_frame, bg=_tc()["log_bg"], fg=_tc()["lb_fg"], selectbackground=_tc()["lb_sel"],
            relief="flat", font=("Consolas", 10), borderwidth=0,
            highlightthickness=0, activestyle="none", selectmode="extended")
        self._ext_listbox.grid(row=0, column=0, sticky="nsew", padx=(8,0), pady=8)
        self._ext_listbox.bind("<<ListboxSelect>>", lambda _: None)
        esb = ctk.CTkScrollbar(ext_frame, command=self._ext_listbox.yview)
        esb.grid(row=0, column=1, sticky="ns", pady=8, padx=(0,4))
        self._ext_listbox.configure(yscrollcommand=esb.set)

        # Add / Remove extensions
        ext_ctrl = ctk.CTkFrame(right, fg_color="transparent")
        ext_ctrl.grid(row=5, column=0, columnspan=2, padx=12, pady=(4,4), sticky="ew")
        ext_ctrl.grid_columnconfigure(0, weight=1)
        self._ext_entry = ctk.CTkEntry(ext_ctrl,
                                        placeholder_text=".ext1  .ext2  (space or comma separated)")
        self._ext_entry.grid(row=0, column=0, sticky="ew", padx=(0,6))
        self._ext_entry.bind("<Return>", lambda _: self._add_extensions())
        ctk.CTkButton(ext_ctrl, text="Add", width=64, height=28,
                      command=self._add_extensions).grid(row=0, column=1, padx=(0,6))
        ctk.CTkButton(ext_ctrl, text="Remove", width=78, height=28,
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self._remove_extensions).grid(row=0, column=2)

        # Delete category
        del_row = ctk.CTkFrame(right, fg_color="transparent")
        del_row.grid(row=6, column=0, columnspan=2, padx=12, pady=(2,12), sticky="ew")
        self._del_btn = ctk.CTkButton(del_row, text="Delete Category",
                                       fg_color="#B83828", hover_color="#8C2A1E",
                                       height=28, width=150,
                                       command=self._delete_category)
        self._del_btn.pack(side="left")
        self._built_in_lbl = ctk.CTkLabel(del_row, text="",
                                           font=ctk.CTkFont(size=10),
                                           text_color="gray50")
        self._built_in_lbl.pack(side="left", padx=(10,0))

        # Bottom save / cancel
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.grid(row=1, column=0, columnspan=2, padx=12, pady=(0,12), sticky="e")
        ctk.CTkButton(btn_bar, text="Cancel", width=100,
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self.destroy).pack(side="left", padx=(0,8))
        ctk.CTkButton(btn_bar, text="Save", width=100,
                      command=self._save).pack(side="left")

        self._refresh_list()

    # ── helpers ────────────────────────────────────────────────────────────────
    def _refresh_list(self):
        self._cat_list.delete(0, "end")
        for cat in self._cats:
            tag = "  [built-in]" if cat.get("built_in") else ""
            self._cat_list.insert("end", f"  {cat['name']}{tag}")

    def _select(self, idx: int):
        if not self._cats or idx >= len(self._cats):
            return
        self._sel_idx = idx
        self._cat_list.selection_clear(0, "end")
        self._cat_list.selection_set(idx)
        cat = self._cats[idx]
        self._name_var.set(cat.get("name", ""))
        self._folder_var.set(cat.get("folder", cat.get("name", "")))
        self._hint_var.set(cat.get("media_hint", "photo"))
        self._ext_listbox.delete(0, "end")
        for ext in sorted(cat.get("extensions", [])):
            self._ext_listbox.insert("end", ext)
        self._update_ext_count()

        built_in = cat.get("built_in", False)
        self._del_btn.configure(state="disabled" if built_in else "normal")
        self._built_in_lbl.configure(
            text="Built-in categories cannot be deleted" if built_in else "")
        # built-in: name/folder still editable
        self._name_entry.configure(state="normal")
        self._folder_entry.configure(state="normal")

    def _on_list_select(self, _event):
        sel = self._cat_list.curselection()
        if sel:
            self._flush_current()
            self._select(sel[0])

    def _flush_current(self):
        if not self._cats:
            return
        cat = self._cats[self._sel_idx]
        name = self._name_var.get().strip()
        if name:
            cat["name"] = name
        folder = self._folder_var.get().strip()
        if folder:
            cat["folder"] = folder
        cat["media_hint"] = self._hint_var.get()
        cat["extensions"] = list(self._ext_listbox.get(0, "end"))
        self._refresh_list()

    def _update_ext_count(self):
        n = self._ext_listbox.size()
        self._ext_count_lbl.configure(text=f"({n} extensions)")

    def _add_extensions(self):
        raw = self._ext_entry.get().strip()
        if not raw:
            return
        existing = set(self._ext_listbox.get(0, "end"))
        for part in raw.replace(",", " ").split():
            ext = part if part.startswith(".") else f".{part}"
            ext = ext.lower()
            if ext not in existing:
                self._ext_listbox.insert("end", ext)
                existing.add(ext)
        self._ext_entry.delete(0, "end")
        self._update_ext_count()

    def _remove_extensions(self):
        for i in reversed(self._ext_listbox.curselection()):
            self._ext_listbox.delete(i)
        self._update_ext_count()

    def _add_category(self):
        self._flush_current()
        new_cat = {"name": "New Category", "folder": "New Category",
                   "media_hint": "photo", "built_in": False, "extensions": []}
        self._cats.append(new_cat)
        self._refresh_list()
        self._select(len(self._cats) - 1)

    def _delete_category(self):
        cat = self._cats[self._sel_idx]
        if cat.get("built_in"):
            return
        if not messagebox.askyesno("Delete Category",
                                    f"Delete '{cat['name']}'?", parent=self):
            return
        self._cats.pop(self._sel_idx)
        self._refresh_list()
        self._select(max(0, self._sel_idx - 1))

    def _save(self):
        self._flush_current()
        for cat in self._cats:
            if not cat.get("name") or not cat.get("folder"):
                messagebox.showwarning("Invalid",
                                       "Category name and folder cannot be empty.",
                                       parent=self)
                return
        self._config["categories"] = self._cats
        self._config.pop("photo_extensions", None)
        self._config.pop("video_extensions", None)
        save_config(self._config)
        self._on_save(self._config)
        self.destroy()


# ── Duplicate History dialog ──────────────────────────────────────────────────

class ResetDedupDialog(ctk.CTkToplevel):
    """Shows both app databases (hashes.db + progress.db) with reset options."""

    def __init__(self, parent, dest_path: str):
        super().__init__(parent)
        self.title("App Memory — Reset")
        self.geometry("620x700")
        self.resizable(True, True)
        self.minsize(560, 500)
        _apply_icon(self)

        self._dest_path   = dest_path.strip()
        self._hash_db:    Path | None = None
        self._ckpt_db:    Path | None = None
        self._hash_count  = 0
        self._ckpt_count  = 0
        self._also_ckpt   = tk.BooleanVar(value=True)
        self._resolve_dbs()
        self._build()
        self.grab_set()

    # ── resolve ───────────────────────────────────────────────────────────────

    def _resolve_dbs(self):
        if not self._dest_path:
            return
        import sqlite3
        org = Path(self._dest_path) / ".organizer"

        h = org / "hashes.db"
        if h.exists():
            self._hash_db = h
            try:
                con = sqlite3.connect(str(h))
                r = con.execute("SELECT COUNT(*) FROM hashes").fetchone()
                self._hash_count = r[0] if r else 0
                con.close()
            except Exception:
                pass

        p = org / "progress.db"
        if p.exists():
            self._ckpt_db = p
            try:
                con = sqlite3.connect(str(p))
                r = con.execute(
                    "SELECT COUNT(*) FROM progress "
                    "WHERE status IN ('moved','duplicate','copied')"
                ).fetchone()
                self._ckpt_count = r[0] if r else 0
                con.close()
            except Exception:
                pass

    # ── build UI ──────────────────────────────────────────────────────────────
    #
    # Layout (3-zone):
    #   row 0  — amber header        [FIXED top]
    #   row 1  — scrollable content  [EXPANDS, scrollable]
    #   row 2  — checkbox + buttons  [FIXED bottom — always visible]
    #

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)   # only scroll area expands

        # ══ ZONE 1: fixed amber header ════════════════════════════════════════
        hdr = ctk.CTkFrame(self, corner_radius=0, fg_color=("#B07020", "#2D2318"))
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="🧠  App Memory — Reset",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=("#FFFFFF", "#F0D090")
                     ).pack(padx=20, pady=(14, 2), anchor="w")
        ctk.CTkLabel(hdr,
                     text="The app uses two databases to track past runs. "
                          "You can clear them here.",
                     font=ctk.CTkFont(size=12),
                     text_color=("#F0D090", "#9A8060")
                     ).pack(padx=20, pady=(0, 14), anchor="w")

        # ══ ZONE 2: scrollable content ════════════════════════════════════════
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        if not self._dest_path:
            ctk.CTkLabel(scroll,
                         text="⚠️  No Destination folder selected.\n"
                              "    Please choose a Destination folder first.",
                         font=ctk.CTkFont(size=12),
                         text_color=("gray45", "gray55"), justify="left"
                         ).pack(padx=20, pady=20, anchor="w")
        else:
            self._build_db_card(
                scroll,
                icon       = "📦",
                title      = "Duplicate History",
                subtitle   = "hashes.db  —  remembers file content to detect duplicates",
                db_path    = self._hash_db,
                count      = self._hash_count,
                count_unit = "unique files fingerprinted",
                note       = "Resetting this clears all duplicate detection.",
            )
            self._build_db_card(
                scroll,
                icon       = "📋",
                title      = "Resume Checkpoint",
                subtitle   = "progress.db  —  remembers which files were already processed",
                db_path    = self._ckpt_db,
                count      = self._ckpt_count,
                count_unit = "files marked as done  (skipped on next Resume run)",
                note       = "⚠  This is why files are still skipped after resetting "
                             "Duplicate History alone.",
                note_color = ("#9A3010", "#E07050"),
            )

            # When SHOULD you reset?
            yes_card = ctk.CTkFrame(scroll, fg_color=("#DFF0DF", "#1C2A1C"), corner_radius=8)
            yes_card.pack(fill="x", padx=16, pady=(10, 0))
            ctk.CTkLabel(yes_card, text="✅  When SHOULD you reset?",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=("#2A6A2A", "#7AB648")
                         ).pack(padx=14, pady=(12, 4), anchor="w")
            for line in (
                "• Starting a completely fresh organization from scratch",
                "• Switching to a new Destination folder",
                "• All files in the Destination have been deleted",
            ):
                ctk.CTkLabel(yes_card, text=line, font=ctk.CTkFont(size=12),
                             text_color=("#3A7A3A", "#9ACC80")
                             ).pack(padx=24, pady=2, anchor="w")
            ctk.CTkFrame(yes_card, height=10, fg_color="transparent").pack()

            # When should you NOT reset?
            no_card = ctk.CTkFrame(scroll, fg_color=("#F5EAD5", "#2E200E"), corner_radius=8)
            no_card.pack(fill="x", padx=16, pady=(10, 16))
            ctk.CTkLabel(no_card, text="⚠️  When should you NOT reset?",
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=("#8A5010", "#E0A030")
                         ).pack(padx=14, pady=(12, 4), anchor="w")
            for line in (
                "• Still using the same Destination folder",
                "• Adding new files to an existing collection",
                "  → Already-organized files may be re-imported as duplicates",
            ):
                ctk.CTkLabel(no_card, text=line, font=ctk.CTkFont(size=12),
                             text_color=("#7A4010", "#C8A060")
                             ).pack(padx=24, pady=2, anchor="w")
            ctk.CTkFrame(no_card, height=10, fg_color="transparent").pack()

        # ══ ZONE 3: fixed bottom — checkbox + buttons (always visible) ════════
        bottom = ctk.CTkFrame(self, corner_radius=0,
                              fg_color=("#D8CDB8", "#231C14"))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        can_reset = bool(self._dest_path and (
            (self._hash_db and self._hash_db.exists() and self._hash_count > 0)
            or (self._ckpt_db and self._ckpt_db.exists() and self._ckpt_count > 0)
        ))

        if self._dest_path:
            ctk.CTkCheckBox(bottom,
                            text="Also clear Resume Checkpoint  "
                                 "(re-process all files on next run)",
                            variable=self._also_ckpt,
                            font=ctk.CTkFont(size=12)
                            ).grid(row=0, column=0, padx=20, pady=(14, 8), sticky="w")

        btn_bar = ctk.CTkFrame(bottom, fg_color="transparent")
        btn_bar.grid(row=1, column=0, padx=20, pady=(0, 16), sticky="e")

        ctk.CTkButton(btn_bar, text="Close", width=100,
                      fg_color=("#7A5535", "#3D3020"),
                      hover_color=("#9A7050", "#4D4028"),
                      command=self.destroy
                      ).pack(side="left", padx=(0, 10))

        self._reset_btn = ctk.CTkButton(
            btn_bar, text="🗑  Reset Memory", width=160,
            fg_color="#B83828" if can_reset else ("#8A7060", "#4A3830"),
            hover_color="#8C2A1E" if can_reset else ("#8A7060", "#4A3830"),
            text_color="#FFFFFF",
            text_color_disabled="#C8B8A8",
            state="normal" if can_reset else "disabled",
            command=self._do_reset)
        self._reset_btn.pack(side="left")

    def _build_db_card(self, parent, icon, title, subtitle,
                       db_path, count, count_unit, note, note_color=None):
        """Render one database info card into *parent* (scrollable frame)."""
        card = ctk.CTkFrame(parent, fg_color=("#DDD0BE", "#2D2318"), corner_radius=8)
        card.pack(fill="x", padx=16, pady=(10, 0))
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card, text=f"{icon}  {title}",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 0), sticky="w")
        ctk.CTkLabel(card, text=subtitle,
                     font=ctk.CTkFont(size=11),
                     text_color=("gray50", "gray55")
                     ).grid(row=1, column=0, columnspan=2, padx=14, pady=(2, 8), sticky="w")
        ctk.CTkFrame(card, height=1, fg_color=("gray70", "#4A3820")
                     ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=14)

        if db_path and count > 0:
            ctk.CTkLabel(card, text="Entries",
                         font=ctk.CTkFont(size=12)
                         ).grid(row=3, column=0, padx=14, pady=(10, 2), sticky="w")
            ctk.CTkLabel(card, text=f"{count:,}",
                         font=ctk.CTkFont(size=20, weight="bold"),
                         text_color=("#B07020", "#E0A030")
                         ).grid(row=3, column=1, padx=8, pady=(10, 2), sticky="w")
            ctk.CTkLabel(card, text=count_unit,
                         font=ctk.CTkFont(size=11),
                         text_color=("gray50", "gray55")
                         ).grid(row=4, column=1, padx=8, pady=(0, 4), sticky="w")
        else:
            status = "✅  Empty — nothing to reset" if db_path else "✅  Not found — nothing to reset"
            ctk.CTkLabel(card, text=status,
                         font=ctk.CTkFont(size=12),
                         text_color=("#3A7A3A", "#7AB648")
                         ).grid(row=3, column=0, columnspan=2, padx=14, pady=(10, 4), sticky="w")

        ctk.CTkLabel(card, text=note,
                     font=ctk.CTkFont(size=11),
                     text_color=note_color or ("gray45", "gray55"),
                     wraplength=520, justify="left"
                     ).grid(row=5, column=0, columnspan=2, padx=14, pady=(4, 12), sticky="w")

    # ── action ────────────────────────────────────────────────────────────────

    def _do_reset(self):
        also_ckpt = self._also_ckpt.get()

        targets: list[tuple[Path, str, int]] = []
        if self._hash_db and self._hash_db.exists() and self._hash_count > 0:
            targets.append((self._hash_db, "Duplicate History (hashes.db)",
                            self._hash_count))
        if also_ckpt and self._ckpt_db and self._ckpt_db.exists() and self._ckpt_count > 0:
            targets.append((self._ckpt_db, "Resume Checkpoint (progress.db)",
                            self._ckpt_count))

        if not targets:
            messagebox.showinfo("Nothing to Reset",
                                "No database files found.", parent=self)
            return

        # custom confirm dialog (clearer than messagebox)
        if not _ConfirmResetDialog(self, targets, self._dest_path).result:
            return

        deleted, errors = [], []
        # delete the main DB plus any SQLite auxiliary files (-wal, -shm,
        # -journal). WAL/SHM hold uncommitted data; if left behind they can
        # resurrect rows the next time SQLite reopens the DB at the same path.
        for db, label, _count in targets:
            try:
                for suffix in ("", "-wal", "-shm", "-journal"):
                    aux = db.parent / (db.name + suffix)
                    if aux.exists():
                        aux.unlink()
                deleted.append(label)
            except Exception as exc:
                errors.append(f"{label}: {exc}")

        if errors:
            messagebox.showerror("Error", "\n".join(errors), parent=self)
        if deleted:
            messagebox.showinfo(
                "Reset Complete",
                "Deleted:\n   • " + "\n   • ".join(deleted)
                + "\n\nThe next Run will start fresh duplicate detection.",
                parent=self)
            self.destroy()


# ── Confirm Reset dialog (custom, very explicit about scope) ──────────────────

class _ConfirmResetDialog(ctk.CTkToplevel):
    """Modal confirmation showing exactly what is / isn't deleted.

    Use:  if _ConfirmResetDialog(parent, targets, dest).result:  ...
    """

    def __init__(self, parent, targets, dest_path):
        super().__init__(parent)
        self.title("Confirm Reset")
        self.geometry("560x540")
        self.resizable(False, False)
        _apply_icon(self)
        self.transient(parent)
        self.result = False
        self._build(targets, dest_path)
        self.grab_set()
        self.wait_window()

    def _build(self, targets, dest_path):
        self.grid_columnconfigure(0, weight=1)

        # ── red header ──
        hdr = ctk.CTkFrame(self, corner_radius=0,
                           fg_color=("#B83828", "#7A1818"))
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="⚠️  Confirm Reset",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color="#FFFFFF"
                     ).pack(padx=20, pady=(14, 2), anchor="w")
        ctk.CTkLabel(hdr, text="Please review carefully — this cannot be undone.",
                     font=ctk.CTkFont(size=11),
                     text_color="#FFD0C0"
                     ).pack(padx=20, pady=(0, 14), anchor="w")

        # ── content body ──
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=18, pady=(14, 0))
        body.grid_columnconfigure(0, weight=1)

        # 🗑 Will be DELETED card
        del_card = ctk.CTkFrame(body, fg_color=("#F8DDD8", "#3A1818"),
                                corner_radius=8,
                                border_color=("#D45030", "#9A3010"),
                                border_width=1)
        del_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(del_card, text="🗑  WILL BE DELETED",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#9A3010", "#E07050")
                     ).pack(padx=14, pady=(10, 4), anchor="w")
        for db, label, count in targets:
            ctk.CTkLabel(del_card,
                         text=f"• {label}  —  {count:,} entries",
                         font=ctk.CTkFont(size=12),
                         text_color=("#7A2010", "#E0A090")
                         ).pack(padx=24, pady=1, anchor="w")
        ctk.CTkLabel(del_card,
                     text="(database files inside the .organizer/ folder)",
                     font=ctk.CTkFont(size=10),
                     text_color=("#7A2010", "#C09090")
                     ).pack(padx=24, pady=(2, 10), anchor="w")

        # 🛡 SAFE card
        safe_card = ctk.CTkFrame(body, fg_color=("#DFF0DF", "#1C2A1C"),
                                 corner_radius=8,
                                 border_color=("#7AB648", "#2A6A2A"),
                                 border_width=1)
        safe_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(safe_card, text="🛡  WILL NOT BE TOUCHED",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=("#2A6A2A", "#7AB648")
                     ).pack(padx=14, pady=(10, 4), anchor="w")
        for line in (
            "• All photo/video files in your Destination folder",
            "• All sub-folders (Photos/, Videos/, Duplicates/, etc.)",
            "• All files in your Source folders",
            "• App settings and configuration",
        ):
            ctk.CTkLabel(safe_card, text=line,
                         font=ctk.CTkFont(size=12),
                         text_color=("#3A7A3A", "#9ACC80")
                         ).pack(padx=24, pady=1, anchor="w")
        ctk.CTkLabel(safe_card,
                     text="✓ Your actual photos and videos are completely safe.",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=("#2A6A2A", "#7AB648")
                     ).pack(padx=14, pady=(6, 10), anchor="w")

        # ── buttons ──
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.grid(row=2, column=0, padx=20, pady=(8, 18), sticky="e")

        ctk.CTkButton(btn_bar, text="Cancel", width=110,
                      fg_color=("#7A5535", "#3D3020"),
                      hover_color=("#9A7050", "#4D4028"),
                      command=self._cancel
                      ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(btn_bar, text="🗑  Yes, Reset Memory", width=180,
                      fg_color="#B83828", hover_color="#8C2A1E",
                      text_color="#FFFFFF",
                      command=self._confirm
                      ).pack(side="left")

    def _cancel(self):
        self.result = False
        self.destroy()

    def _confirm(self):
        self.result = True
        self.destroy()


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(ctk.CTkToplevel):
    """Unified preferences — appearance, sound, notifications."""

    def __init__(self, parent, settings: dict, sound: SoundEngine, on_save):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("520x620")
        self.resizable(False, False)
        _apply_icon(self)

        self._settings = dict(settings)   # work on a copy
        self._sound    = sound
        self._on_save  = on_save
        self._build()
        self.grab_set()

    # ── build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── header ──
        hdr = ctk.CTkFrame(self, corner_radius=0, fg_color=("#B07020", "#2D2318"))
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="⚙  Settings",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=("#FFFFFF", "#F0D090")
                     ).pack(padx=20, pady=(14, 2), anchor="w")
        ctk.CTkLabel(hdr, text="Appearance · Sound · Notifications",
                     font=ctk.CTkFont(size=11),
                     text_color=("#F0D090", "#9A8060")
                     ).pack(padx=20, pady=(0, 14), anchor="w")

        # ── scrollable body ──
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        body.grid_columnconfigure(0, weight=1)

        self._section(body, "🎨  Appearance")
        self._build_appearance(body)

        self._section(body, "🔊  Sound")
        self._build_sound(body)

        self._section(body, "🔔  Notifications")
        self._build_notifications(body)

        self._section(body, "🌐  Language")
        self._build_language(body)

        # ── fixed bottom buttons ──
        bottom = ctk.CTkFrame(self, corner_radius=0,
                              fg_color=("#D8CDB8", "#231C14"))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        bb = ctk.CTkFrame(bottom, fg_color="transparent")
        bb.grid(row=0, column=0, padx=20, pady=14, sticky="e")

        ctk.CTkButton(bb, text="Cancel", width=100,
                      fg_color=("#7A5535", "#3D3020"),
                      hover_color=("#9A7050", "#4D4028"),
                      command=self.destroy
                      ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(bb, text="💾  Save", width=120,
                      command=self._save
                      ).pack(side="left")

    def _section(self, parent, title: str):
        ctk.CTkLabel(parent, text=title,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("#7A4A10", "#E0A030")
                     ).pack(padx=18, pady=(14, 6), anchor="w")

    def _card(self, parent) -> ctk.CTkFrame:
        c = ctk.CTkFrame(parent, fg_color=("#DDD0BE", "#2D2318"), corner_radius=8)
        c.pack(fill="x", padx=18, pady=(0, 4))
        return c

    # ── appearance section ────────────────────────────────────────────────────

    def _build_appearance(self, parent):
        c = self._card(parent)
        ctk.CTkLabel(c, text="Theme",
                     font=ctk.CTkFont(size=12)
                     ).pack(padx=14, pady=(12, 4), anchor="w")
        self._theme_var = tk.StringVar(value=self._settings.get("theme", "dark"))
        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(padx=14, pady=(0, 12), anchor="w")
        for value, label in (("dark", "🌙 Dark"),
                             ("light", "☀ Light"),
                             ("system", "🖥 System")):
            ctk.CTkRadioButton(row, text=label, variable=self._theme_var,
                               value=value
                               ).pack(side="left", padx=(0, 16))

    # ── sound section ─────────────────────────────────────────────────────────

    def _build_sound(self, parent):
        c = self._card(parent)

        # enable toggle
        self._snd_enabled = tk.BooleanVar(
            value=self._settings.get("sound_enabled", False))
        ctk.CTkCheckBox(c, text="Enable sound effects",
                        variable=self._snd_enabled,
                        font=ctk.CTkFont(size=12)
                        ).pack(padx=14, pady=(12, 8), anchor="w")

        # theme dropdown
        theme_row = ctk.CTkFrame(c, fg_color="transparent")
        theme_row.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(theme_row, text="Theme",
                     font=ctk.CTkFont(size=12), width=80, anchor="w"
                     ).pack(side="left")
        self._snd_theme = tk.StringVar(
            value=self._settings.get("sound_theme", "nature"))
        ctk.CTkOptionMenu(theme_row, variable=self._snd_theme,
                          values=["nature", "minimal", "none"],
                          width=140
                          ).pack(side="left", padx=(8, 0))

        # volume slider
        vol_row = ctk.CTkFrame(c, fg_color="transparent")
        vol_row.pack(fill="x", padx=14, pady=(0, 8))
        ctk.CTkLabel(vol_row, text="Volume",
                     font=ctk.CTkFont(size=12), width=80, anchor="w"
                     ).pack(side="left")
        self._snd_vol = tk.DoubleVar(
            value=self._settings.get("sound_volume", 0.6))
        self._vol_lbl = ctk.CTkLabel(vol_row,
                                     text=f"{int(self._snd_vol.get()*100)}%",
                                     font=ctk.CTkFont(size=11), width=40)
        self._vol_lbl.pack(side="right")
        ctk.CTkSlider(vol_row, from_=0, to=1, variable=self._snd_vol,
                      command=lambda v: self._vol_lbl.configure(
                          text=f"{int(float(v)*100)}%")
                      ).pack(side="left", fill="x", expand=True, padx=(8, 8))

        # preview buttons
        prev_row = ctk.CTkFrame(c, fg_color="transparent")
        prev_row.pack(fill="x", padx=14, pady=(4, 12))
        ctk.CTkLabel(prev_row, text="Test:",
                     font=ctk.CTkFont(size=12), width=80, anchor="w"
                     ).pack(side="left")
        for evt, label in (("start", "▶ Start"),
                           ("complete", "✓ Done"),
                           ("error", "⚠ Error")):
            ctk.CTkButton(prev_row, text=label, width=80, height=26,
                          fg_color=("#7A5535", "#3D3020"),
                          hover_color=("#9A7050", "#4D4028"),
                          command=lambda e=evt: self._preview(e)
                          ).pack(side="left", padx=(4, 0))

        # hint
        ctk.CTkLabel(c,
                     text="Sounds are synthesized — no internet or assets needed.",
                     font=ctk.CTkFont(size=10),
                     text_color=("gray45", "gray55")
                     ).pack(padx=14, pady=(0, 10), anchor="w")

    def _preview(self, event: str):
        # apply volume to engine before preview so user hears the new level
        self._sound.configure(
            enabled=True,
            theme=self._snd_theme.get(),
            volume=self._snd_vol.get(),
        )
        self._sound.preview(self._snd_theme.get(), event)

    # ── notifications section ─────────────────────────────────────────────────

    def _build_notifications(self, parent):
        c = self._card(parent)
        self._notify_var = tk.BooleanVar(
            value=self._settings.get("notify_on_done", True))
        ctk.CTkCheckBox(c,
                        text="Show system notification when run finishes",
                        variable=self._notify_var,
                        font=ctk.CTkFont(size=12)
                        ).pack(padx=14, pady=(12, 4), anchor="w")
        ctk.CTkLabel(c,
                     text="Useful when the window is minimised or in the system tray.",
                     font=ctk.CTkFont(size=10),
                     text_color=("gray45", "gray55")
                     ).pack(padx=14, pady=(0, 12), anchor="w")

    # ── language section ──────────────────────────────────────────────────────

    def _build_language(self, parent):
        c = self._card(parent)
        ctk.CTkLabel(c, text="Interface language",
                     font=ctk.CTkFont(size=12)
                     ).pack(padx=14, pady=(12, 4), anchor="w")
        ctk.CTkLabel(c,
                     text="🇬🇧  English  (Thai coming in v2.0)",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray45", "gray55")
                     ).pack(padx=14, pady=(0, 12), anchor="w")

    # ── save ──────────────────────────────────────────────────────────────────

    def _save(self):
        self._settings["theme"]          = self._theme_var.get()
        self._settings["sound_enabled"]  = self._snd_enabled.get()
        self._settings["sound_theme"]    = self._snd_theme.get()
        self._settings["sound_volume"]   = round(self._snd_vol.get(), 2)
        self._settings["notify_on_done"] = self._notify_var.get()
        self._on_save(self._settings)
        self.destroy()


# ── splash screen ─────────────────────────────────────────────────────────────

class SplashScreen(tk.Toplevel):
    """Borderless splash screen with rounded corners via Win32 SetWindowRgn.

    Uses plain tk.Toplevel (not CTkToplevel) so that winfo_id() returns
    the actual top-level HWND directly — no internal CTk frame wrapping
    that would cause GetParent() to land on the wrong window.
    """
    SPLASH_MS = 2500
    CORNER_R  = 20   # corner ellipse radius (pixels)

    def __init__(self, parent, on_done):
        super().__init__(parent)
        self._on_done = on_done
        self._closed  = False

        self.configure(bg="#000000")   # explicit black — no white leaking
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        photo, self._sw, self._sh = self._load_photo()

        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        self.geometry(f"{self._sw}x{self._sh}"
                      f"+{(scr_w - self._sw) // 2}+{(scr_h - self._sh) // 2}")
        self.resizable(False, False)

        if photo:
            canvas = tk.Canvas(self, width=self._sw, height=self._sh,
                               bg="#000000", highlightthickness=0, borderwidth=0)
            canvas.pack(fill="both", expand=True)
            canvas.create_image(0, 0, anchor="nw", image=photo)
            canvas._photo = photo   # prevent GC

        self.bind("<Button-1>", lambda _e: self._close())
        # Give the window a moment to fully render before clipping
        self.after(80, self._round_corners)
        self.after(self.SPLASH_MS, self._close)

    # ── image loader ──────────────────────────────────────────────────────────

    def _load_photo(self):
        try:
            from PIL import Image as _I, ImageTk as _ITk
            img = _I.open(BASE_DIR / "assets" / "memory_nest_flash_screen.png")
            max_w = 800
            ratio = max_w / img.width
            w, h  = max_w, int(img.height * ratio)
            img   = img.resize((w, h), _I.LANCZOS)
            return _ITk.PhotoImage(img), w, h
        except Exception:
            return None, 800, 500

    # ── rounded corners ───────────────────────────────────────────────────────

    def _round_corners(self):
        """SetWindowRgn clips window to a rounded rect at Win32 level.
        Pixels outside the region are fully transparent — no colour fringing.
        DwmSetWindowAttribute is attempted on top for Win11 compositor smoothing.
        """
        try:
            import ctypes
            hwnd = self.winfo_id()   # correct top-level HWND (plain Toplevel)
            w, h = self._sw, self._sh
            d    = self.CORNER_R * 2  # ellipse diameter for CreateRoundRectRgn

            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                0, 0, w + 1, h + 1, d, d
            )
            ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)

            # Win11 bonus: ask DWM to smooth the clipped edges further
            try:
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_ROUND = 2
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_ROUND)), 4
                )
            except Exception:
                pass
        except Exception:
            pass

    # ── close ─────────────────────────────────────────────────────────────────

    def _close(self):
        if self._closed:
            return
        self._closed = True
        self.destroy()
        self._on_done()


# ── main application ───────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.withdraw()   # hide until splash is done

        self.title("MemoryNest Sync")
        self.geometry("1200x820")
        self.minsize(1000, 680)

        # window icon
        ico = BASE_DIR / "assets" / "icon.ico"
        if ico.exists():
            try:
                self.iconbitmap(str(ico))
            except Exception:
                pass

        self._settings        = load_settings()
        self._config          = load_config()
        self._worker: threading.Thread | None = None
        self._organizer: Organizer | None     = None
        self._evt_queue: queue.Queue[OrganizerEvent] = queue.Queue()
        self._total_files     = 0
        self._source_paths: list[Path] = []
        self._pending_badge   = 0   # unresolved device count
        self._cnt_photos      = 0
        self._cnt_videos      = 0
        self._cnt_dupes       = 0
        self._cnt_errors      = 0
        self._cnt_resumed     = 0

        # animation state (v1.1) — smooth interpolation toward targets
        self._prog_target_overall = 0.0
        self._prog_target_current = 0.0
        self._pulse_phase = 0.0       # radians, advanced each tick when running
        self._pulse_active = False    # True while a run is in progress

        # apply saved theme
        ctk.set_appearance_mode(self._settings.get("theme", "dark"))
        ctk.set_default_color_theme(str(BASE_DIR / "assets" / "nest_theme.json"))

        # sound engine (renders WAVs on first launch — quiet by default)
        self._sound = SoundEngine(BASE_DIR / "assets" / "sounds")
        self._apply_sound_settings()

        self._build_layout()
        self._poll_events()
        self._animate()                # micro-animation tick (~60 fps)
        self._setup_tray()
        SplashScreen(self, self.deiconify)

    # ── sound helpers ─────────────────────────────────────────────────────────

    def _apply_sound_settings(self):
        self._sound.configure(
            enabled = self._settings.get("sound_enabled", False),
            theme   = self._settings.get("sound_theme", "nature"),
            volume  = self._settings.get("sound_volume", 0.6),
        )

    def _play_sound(self, event: str):
        try:
            self._sound.play(event)
        except Exception:
            pass

    def _maybe_notify(self, stats: dict):
        """Show system tray balloon when run finishes (only if window not focused)."""
        try:
            # don't notify when user is actively watching the window
            if self.focus_displayof() is not None and self.state() == "normal":
                return
            if not self._tray_icon:
                return
            moved = stats.get("moved", 0)
            dupes = stats.get("duplicates", 0)
            errs  = stats.get("errors", 0)
            title = "MemoryNest Sync — Run finished"
            msg   = (f"Moved/Copied: {moved:,}  ·  Duplicates: {dupes:,}"
                     + (f"  ·  Errors: {errs:,}" if errs else ""))
            self._tray_icon.notify(msg, title)
        except Exception:
            pass

    # ── system tray ───────────────────────────────────────────────────────────

    def _setup_tray(self):
        try:
            import pystray
            from PIL import Image as _PILImageTray
            ico_path = BASE_DIR / "assets" / "icon.ico"
            if ico_path.exists():
                tray_img = _PILImageTray.open(ico_path).resize((64, 64))
            else:
                tray_img = _PILImageTray.new("RGB", (64, 64), "#1a73e8")

            menu = pystray.Menu(
                pystray.MenuItem("Show MemoryNest Sync", self._show_window, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._quit_app),
            )
            self._tray_icon = pystray.Icon("MemoryNest Sync", tray_img,
                                           "MemoryNest Sync", menu)
            self._tray_icon.run_detached()
            self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        except Exception:
            self._tray_icon = None

    def _hide_to_tray(self):
        self.withdraw()

    def _show_window(self, *_):
        self.after(0, self.deiconify)
        self.after(0, self.lift)

    def _quit_app(self, *_):
        if self._tray_icon:
            self._tray_icon.stop()
        self.after(0, self.destroy)

    # ── layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=0, minsize=330)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)  # top bar
        self.grid_rowconfigure(1, weight=0)  # amber separator
        self.grid_rowconfigure(2, weight=1)  # main content

        self._build_topbar()
        ctk.CTkFrame(self, height=2, corner_radius=0,
                     fg_color=("#B07020", "#C8882A")
                     ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        self._build_left_panel()
        self._build_right_panel()

    # ─ top bar ────────────────────────────────────────────────────────────────

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(bar, text="🪺  MemoryNest Sync",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=("#7A4A10", "#C8882A"),
                     ).grid(row=0, column=0, padx=16, pady=8, sticky="w")

        # version — right side, beside theme button
        ctk.CTkLabel(bar, text=f"v{APP_VERSION}",
                     font=ctk.CTkFont(size=10),
                     text_color=("#9A7850", "#9A8060"),
                     ).grid(row=0, column=1, padx=(0, 6), pady=8, sticky="e")

        # theme cycle button
        self._theme_btn = ctk.CTkButton(
            bar, text=self._theme_icon(), width=110, height=28,
            fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
            font=ctk.CTkFont(size=13),
            command=self._cycle_theme)
        self._theme_btn.grid(row=0, column=2, padx=(0, 6), pady=6)

        # settings (gear) button
        ctk.CTkButton(
            bar, text="⚙", width=36, height=28,
            fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
            font=ctk.CTkFont(size=15),
            command=self._open_settings
            ).grid(row=0, column=3, padx=(0, 12), pady=6)

    def _theme_icon(self) -> str:
        icons = {"dark": "🌙  Dark", "light": "☀️  Light", "system": "🖥  System"}
        return icons.get(self._settings.get("theme", "dark"), "🌙  Dark")

    def _cycle_theme(self):
        order = ["dark", "light", "system"]
        cur   = self._settings.get("theme", "dark")
        nxt   = order[(order.index(cur) + 1) % len(order)]
        self._settings["theme"] = nxt
        save_settings(self._settings)
        ctk.set_appearance_mode(nxt)
        self._theme_btn.configure(text=self._theme_icon())
        self._apply_listbox_theme()

    def _apply_listbox_theme(self):
        c = _tc()
        self._src_listbox.configure(bg=c["lb_bg"], fg=c["lb_fg"],
                                    selectbackground=c["lb_sel"])
        self._log_text.configure(bg=c["log_bg"], fg=c["log_fg"])

    # ─ left panel ─────────────────────────────────────────────────────────────

    def _build_left_panel(self):
        left = ctk.CTkFrame(self, width=330)
        left.grid(row=2, column=0, padx=(12, 6), pady=(0, 12), sticky="nsew")
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)

        # Source folders
        ctk.CTkLabel(left, text="Source Folders",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        src_frame = ctk.CTkFrame(left, fg_color="transparent")
        src_frame.grid(row=1, column=0, padx=12, sticky="ew")
        src_frame.grid_columnconfigure(0, weight=1)

        self._src_listbox = tk.Listbox(
            src_frame, height=4, bg=_tc()["lb_bg"], fg=_tc()["lb_fg"],
            selectbackground=_tc()["lb_sel"], relief="flat",
            font=("Consolas", 9), borderwidth=0, highlightthickness=1,
            highlightbackground="#6A5538", activestyle="none",
        )
        self._src_listbox.grid(row=0, column=0, sticky="ew")

        src_btn = ctk.CTkFrame(src_frame, fg_color="transparent")
        src_btn.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkButton(src_btn, text="+ Add Folder", height=28,
                      command=self._add_source).pack(side="left", padx=(0, 4))
        ctk.CTkButton(src_btn, text="Remove", height=28, width=80,
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self._remove_source).pack(side="left")

        # Destination
        ctk.CTkLabel(left, text="Destination Folder",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=2, column=0, padx=12, pady=(12, 4), sticky="w")

        dest_frame = ctk.CTkFrame(left, fg_color="transparent")
        dest_frame.grid(row=3, column=0, padx=12, sticky="ew")
        dest_frame.grid_columnconfigure(0, weight=1)

        self._dest_var = tk.StringVar()
        ctk.CTkEntry(dest_frame, textvariable=self._dest_var,
                     placeholder_text="Select destination…"
                     ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(dest_frame, text="Browse", height=28, width=72,
                      command=self._browse_dest
                      ).grid(row=0, column=1, padx=(6, 0))

        # Options
        ctk.CTkLabel(left, text="Options",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=4, column=0, padx=12, pady=(12, 4), sticky="w")

        opt = ctk.CTkFrame(left, fg_color="transparent")
        opt.grid(row=5, column=0, padx=12, sticky="ew")

        self._dry_run_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt, text="Dry Run  (preview only — no files touched)",
                        variable=self._dry_run_var).pack(anchor="w", pady=2)

        self._dedup_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt, text="Detect & quarantine duplicates",
                        variable=self._dedup_var).pack(anchor="w", pady=2)

        self._subfolder_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt, text="Include sub-folders",
                        variable=self._subfolder_var).pack(anchor="w", pady=2)

        self._resume_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt, text="Resume  (skip already-processed files)",
                        variable=self._resume_var).pack(anchor="w", pady=2)

        # Move / Copy
        op_frame = ctk.CTkFrame(opt, fg_color="transparent")
        op_frame.pack(anchor="w", pady=(8, 2), fill="x")
        ctk.CTkLabel(op_frame, text="Operation:",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 10))

        self._op_var = tk.StringVar(value=self._settings.get("operation", "copy"))
        ctk.CTkRadioButton(op_frame, text="Copy", variable=self._op_var, value="copy",
                           command=self._save_op).pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(op_frame, text="Move", variable=self._op_var, value="move",
                           command=self._save_op).pack(side="left")

        # Threads
        thread_frame = ctk.CTkFrame(opt, fg_color="transparent")
        thread_frame.pack(anchor="w", pady=(4, 0), fill="x")
        ctk.CTkLabel(thread_frame, text="Metadata threads:",
                     font=ctk.CTkFont(size=11)).pack(side="left")
        self._thread_var = tk.IntVar(value=4)
        self._thread_label = ctk.CTkLabel(thread_frame, text="4",
                                          font=ctk.CTkFont(size=11), width=24)
        self._thread_label.pack(side="right")
        ctk.CTkSlider(thread_frame, from_=1, to=8, number_of_steps=7,
                      variable=self._thread_var, width=110,
                      command=lambda v: self._thread_label.configure(text=str(int(v)))
                      ).pack(side="right", padx=(4, 4))

        # Tool buttons
        tools = ctk.CTkFrame(left, fg_color="transparent")
        tools.grid(row=6, column=0, padx=12, pady=(12, 4), sticky="ew")
        tools.grid_columnconfigure((0, 1), weight=1)

        self._dev_mgr_btn = ctk.CTkButton(
            tools, text="🗺  Device Manager",
            fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
            command=self._open_device_manager)
        self._dev_mgr_btn.grid(row=0, column=0, padx=(0, 4), pady=(0,4), sticky="ew")

        ctk.CTkButton(tools, text="🗂  Folder Structure",
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self._open_folder_structure
                      ).grid(row=0, column=1, padx=(4, 0), pady=(0,4), sticky="ew")

        ctk.CTkButton(tools, text="🏷  Category Manager",
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self._open_category_manager
                      ).grid(row=1, column=0, columnspan=2, pady=(0, 4), sticky="ew")

        ctk.CTkButton(tools, text="🗑  Duplicate History",
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self._open_reset_dedup
                      ).grid(row=2, column=0, columnspan=2, pady=(0, 0), sticky="ew")

        # Start / Stop
        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.grid(row=7, column=0, padx=12, pady=(10, 14), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self._btn_start = ctk.CTkButton(
            btn_frame, text="▶  Start", height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start)
        self._btn_start.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._btn_stop = ctk.CTkButton(
            btn_frame, text="⏹  Stop", height=38,
            fg_color="#B83828", hover_color="#8C2A1E",
            text_color="#FFFFFF", text_color_disabled="#C0A0A0",
            state="disabled", command=self._stop)
        self._btn_stop.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self._update_badge()

        # ── Logo / ZigGaZa credit ──────────────────────────────────────────────
        left.grid_rowconfigure(8, weight=1)
        logo_frame = ctk.CTkFrame(left, fg_color="transparent")
        logo_frame.grid(row=8, column=0, padx=0, pady=0, sticky="nsew")
        logo_frame.grid_columnconfigure(0, weight=1)
        logo_frame.grid_rowconfigure(0, weight=1)

        try:
            from PIL import Image as _PILImage
            _img = _PILImage.open(BASE_DIR / "assets" / "ziggaza_logo.png")
            _w = 270
            _h = int(_w * _img.height / _img.width)
            _ctk_img = ctk.CTkImage(light_image=_img, dark_image=_img, size=(_w, _h))
            ctk.CTkLabel(logo_frame, image=_ctk_img, text="",
                         fg_color="transparent"
                         ).grid(row=0, column=0, sticky="s", padx=0, pady=(0, 2))
        except Exception:
            pass

        ctk.CTkLabel(logo_frame,
                     text="POWERED BY  ZigGaZa STUDIO",
                     font=ctk.CTkFont(size=9),
                     text_color="gray45"
                     ).grid(row=1, column=0, pady=(0, 2))

        # ── clickable website link ──────────────────────────────────────────
        _WEBSITE = "https://ziggaza.github.io/memorynest-sync/"
        web_lbl = tk.Label(logo_frame,
                           text="🌐  memorynest-sync",
                           font=("Segoe UI", 8, "underline"),
                           fg="#C8882A", bg="#231C14",
                           cursor="hand2", borderwidth=0)
        web_lbl.grid(row=2, column=0, pady=(0, 10))
        web_lbl.bind("<Button-1>",
                     lambda _e: __import__("webbrowser").open(_WEBSITE))
        # keep bg in sync with theme (light mode uses lighter bg)
        def _sync_web_bg(lbl=web_lbl):
            dark = ctk.get_appearance_mode().lower() == "dark"
            lbl.configure(bg="#231C14" if dark else "#EAE0D0",
                          fg="#C8882A" if dark else "#8A5A10")
        _sync_web_bg()
        # re-sync when theme changes — piggyback on existing cycle_theme
        _orig_cycle = self._cycle_theme
        def _patched_cycle(orig=_orig_cycle, sync=_sync_web_bg):
            orig()
            self.after(50, sync)
        self._cycle_theme = _patched_cycle
        self._theme_btn.configure(command=_patched_cycle)

    # ─ right panel ────────────────────────────────────────────────────────────

    def _build_right_panel(self):
        right = ctk.CTkFrame(self)
        right.grid(row=2, column=1, padx=(6, 12), pady=(0, 12), sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # Stats — 2 rows × 3 cols grid so they always fit at any window width
        stats_frame = ctk.CTkFrame(right, fg_color="transparent")
        stats_frame.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        stats_frame.grid_columnconfigure((0, 1, 2), weight=1)

        _STAT_DEFS = [
            # (icon, label, key, accent_color, grid_row, grid_col)
            ("🪺", "Total",   "total",   "#C8882A", 0, 0),
            ("📷", "Photos",  "photos",  "#C8882A", 0, 1),
            ("🎬", "Videos",  "videos",  "#C8882A", 0, 2),
            ("🗂", "Dupes",   "dupes",   "#D4A030", 1, 0),
            ("⏩", "Resumed", "resumed", "#7AB648", 1, 1),
            ("⚠️", "Errors",  "errors",  "#D45030", 1, 2),
        ]
        self._stat_vars = {}
        for icon, lbl, key, accent, gr, gc in _STAT_DEFS:
            pad_x = (0, 6) if gc < 2 else (0, 0)
            pad_y = (0, 6) if gr == 0 else (0, 0)
            f = ctk.CTkFrame(stats_frame, fg_color=("#DDD0BE", "#2D2318"), corner_radius=8)
            f.grid(row=gr, column=gc, padx=pad_x, pady=pad_y, sticky="ew")
            # top accent bar
            ctk.CTkFrame(f, height=3, corner_radius=2, fg_color=accent
                         ).pack(fill="x", padx=6, pady=(4, 0))
            ctk.CTkLabel(f, text=icon, font=ctk.CTkFont(size=15)
                         ).pack(pady=(3, 0))
            var = tk.StringVar(value="—")
            self._stat_vars[key] = var
            ctk.CTkLabel(f, textvariable=var,
                         font=ctk.CTkFont(size=24, weight="bold"),
                         text_color=("#5A3A10", "#F0D090")).pack()
            ctk.CTkLabel(f, text=lbl,
                         font=ctk.CTkFont(size=11),
                         text_color=("#8A7055", "#9A8060")).pack(pady=(0, 5))

        # Log panel
        log_outer = ctk.CTkFrame(right)
        log_outer.grid(row=1, column=0, padx=12, pady=(4, 4), sticky="nsew")
        log_outer.grid_columnconfigure(0, weight=1)
        log_outer.grid_rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_outer, fg_color="transparent")
        log_hdr.grid(row=0, column=0, padx=8, pady=(8, 2), sticky="ew")
        ctk.CTkLabel(log_hdr, text="Activity Log",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkButton(log_hdr, text="Clear", width=60, height=24,
                      fg_color=("#7A5535", "#3D3020"), hover_color=("#9A7050", "#4D4028"),
                      command=self._clear_log).pack(side="right")

        self._log_text = tk.Text(
            log_outer, bg=_tc()["log_bg"], fg=_tc()["log_fg"], wrap="none",
            font=("Consolas", 9), relief="flat", state="disabled", borderwidth=0)
        self._log_text.grid(row=1, column=0, sticky="nsew", padx=8)
        sb = ctk.CTkScrollbar(log_outer, command=self._log_text.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self._log_text.configure(yscrollcommand=sb.set)

        for tag, color in [("ok","#7AB648"),("dupe","#C8882A"),
                           ("error","#D45030"),("info","#9A8870"),("head","#E0A030")]:
            self._log_text.tag_configure(tag, foreground=color)

        # Progress bars
        prog = ctk.CTkFrame(right, fg_color="transparent")
        prog.grid(row=2, column=0, padx=12, pady=(4, 12), sticky="ew")
        prog.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(prog, text="Overall", width=60, anchor="e",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0,8))
        self._prog_overall = ctk.CTkProgressBar(prog, height=14)
        self._prog_overall.grid(row=0, column=1, sticky="ew")
        self._prog_overall.set(0)
        self._prog_label = ctk.CTkLabel(prog, text="0 / 0", width=80, anchor="w",
                                        font=ctk.CTkFont(size=11))
        self._prog_label.grid(row=0, column=2, padx=(8,0))
        self._speed_label = ctk.CTkLabel(prog, text="", width=80, anchor="w",
                                         font=ctk.CTkFont(size=10), text_color="gray60")
        self._speed_label.grid(row=0, column=3, padx=(4,0))

        ctk.CTkLabel(prog, text="Current", width=60, anchor="e",
                     font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=(0,8), pady=(4,0))
        self._prog_current = ctk.CTkProgressBar(prog, height=8)
        self._prog_current.grid(row=1, column=1, sticky="ew", pady=(4,0))
        self._prog_current.set(0)
        self._current_label = ctk.CTkLabel(prog, text="—", width=80, anchor="w",
                                           font=ctk.CTkFont(size=10), text_color="gray60")
        self._current_label.grid(row=1, column=2, padx=(8,0), pady=(4,0))

    # ── source management ─────────────────────────────────────────────────────

    def _add_source(self):
        path = filedialog.askdirectory(title="Select Source Folder")
        if path:
            p = Path(path)
            if str(p) not in self._src_listbox.get(0, "end"):
                self._src_listbox.insert("end", str(p))
                self._source_paths.append(p)

    def _remove_source(self):
        sel = self._src_listbox.curselection()
        if sel:
            idx = sel[0]
            self._src_listbox.delete(idx)
            self._source_paths.pop(idx)

    def _browse_dest(self):
        path = filedialog.askdirectory(title="Select Destination Folder")
        if path:
            self._dest_var.set(path)

    def _save_op(self):
        self._settings["operation"] = self._op_var.get()
        save_settings(self._settings)

    # ── device manager ────────────────────────────────────────────────────────

    def _open_device_manager(self):
        DeviceManagerDialog(self, self._config, on_save=self._reload_config)

    def _open_folder_structure(self):
        FolderStructureDialog(self, self._config, on_save=self._reload_config)

    def _open_category_manager(self):
        CategoryManagerDialog(self, self._config, on_save=self._reload_config)

    def _open_reset_dedup(self):
        ResetDedupDialog(self, self._dest_var.get())

    def _open_settings(self):
        SettingsDialog(self, self._settings, self._sound,
                       on_save=self._apply_new_settings)

    def _apply_new_settings(self, new_settings: dict):
        old_theme = self._settings.get("theme")
        self._settings = new_settings
        save_settings(self._settings)
        # apply changes live
        if new_settings.get("theme") != old_theme:
            ctk.set_appearance_mode(new_settings["theme"])
            self._theme_btn.configure(text=self._theme_icon())
            self._apply_listbox_theme()
        self._apply_sound_settings()

    def _reload_config(self, new_cfg: dict):
        self._config = new_cfg
        self._update_badge()
        self._log("info", "Config reloaded.")

    def _auto_save_unresolved(self, unresolved: dict[str, str]):
        """Save new EXIF keys → config and update badge. Called after each run."""
        if not unresolved:
            return
        mappings  = self._config.setdefault("device_mappings", {})
        auto_keys = set(self._config.setdefault("auto_detected_keys", []))
        added = 0
        for key, raw_name in unresolved.items():
            if key not in mappings:
                mappings[key] = raw_name
                auto_keys.add(key)
                added += 1
        self._config["auto_detected_keys"] = list(auto_keys)
        if added:
            save_config(self._config)
            self._log("info",
                      f"{added} new device(s) auto-added to Device Manager "
                      f"— open Device Manager to set folder names")
        self._update_badge()

    def _update_badge(self):
        count = len(self._config.get("auto_detected_keys", []))
        if count:
            self._dev_mgr_btn.configure(text=f"🗺  Device Manager  ({count})",
                                        text_color="#F0D090")
        else:
            self._dev_mgr_btn.configure(text="🗺  Device Manager",
                                        text_color=["#FFFFFF", "#F0E0C0"])

    # ── run / stop ────────────────────────────────────────────────────────────

    def _start(self):
        if not self._source_paths:
            messagebox.showwarning("No Source",
                                   "Please add at least one source folder.")
            return
        dest_str = self._dest_var.get().strip()
        if not dest_str:
            messagebox.showwarning("No Destination",
                                   "Please select a destination folder.")
            return

        dest    = Path(dest_str)
        dry_run = self._dry_run_var.get()
        copy_mode = (self._op_var.get() == "copy")

        if not dry_run:
            op_word = "COPIED to destination (source kept)" if copy_mode \
                      else "MOVED (source files will be removed)"
            ok = messagebox.askyesno(
                f"Confirm {'Copy' if copy_mode else 'Move'}",
                f"Dry Run is OFF.\n\nFiles will be {op_word}.\n\nContinue?")
            if not ok:
                return

        self._reset_ui()
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._play_sound("start")

        self._organizer = Organizer(
            config    = self._config,
            dest_root = dest,
            dry_run   = dry_run,
            copy_mode = copy_mode,
            resume    = self._resume_var.get(),
            workers   = self._thread_var.get(),
            on_event  = self._evt_queue.put,
        )
        self._worker = threading.Thread(
            target=self._worker_run,
            args=(list(self._source_paths),),
            daemon=True,
        )
        self._worker.start()

    def _worker_run(self, sources):
        try:
            self._organizer.run(sources)
        except Exception as exc:
            self._evt_queue.put(OrganizerEvent(
                kind=EventKind.DONE,
                stats={"error": str(exc), "total": 0, "moved": 0,
                       "duplicates": 0, "errors": 1, "skipped": 0,
                       "elapsed_sec": 0, "resumed": 0},
            ))

    def _stop(self):
        if self._organizer:
            self._organizer.stop()
        self._btn_stop.configure(state="disabled")
        self._log("info", "Stop requested — finishing current file…")

    # ── event polling ─────────────────────────────────────────────────────────

    def _poll_events(self):
        try:
            while True:
                evt: OrganizerEvent = self._evt_queue.get_nowait()

                if evt.kind == EventKind.SCANNED:
                    self._total_files = evt.total
                    op = self._op_var.get().upper()
                    mode = "DRY RUN" if self._dry_run_var.get() else op
                    msg  = f"Scan complete — {evt.total} files  [{mode}]"
                    if evt.already_done:
                        msg += f"  ({evt.already_done} already done)"
                    self._log("head", msg)
                    self._stat_vars["total"].set(str(evt.total))

                elif evt.kind == EventKind.RESUMED:
                    self._cnt_resumed = evt.already_done
                    self._stat_vars["resumed"].set(str(self._cnt_resumed))
                    self._log("info",
                              f"Resume: skipping {self._cnt_resumed} already-processed files")

                elif evt.kind == EventKind.PROGRESS:
                    idx   = evt.index
                    total = self._total_files or 1
                    # set targets — _animate() will interpolate smoothly
                    self._prog_target_overall = idx / total
                    self._prog_target_current = (idx % 20) / 20
                    self._prog_label.configure(text=f"{idx} / {total}")
                    if evt.files_per_sec > 0:
                        self._speed_label.configure(
                            text=f"{evt.files_per_sec:.1f} files/s")
                    fname = Path(evt.src_path).name
                    self._current_label.configure(text=fname)
                    self._pulse_active = True

                    if evt.status in ("moved", "copied", "dry_run"):
                        if evt.media_type == "Videos":
                            self._cnt_videos += 1
                        else:
                            self._cnt_photos += 1
                        pfx = {"moved":"MOV","copied":"CPY","dry_run":"DRY"
                               }.get(evt.status, evt.status[:3].upper())
                        dest_rel = self._rel(evt.dest_path)
                        self._log("ok",
                                  f"[{pfx}] {fname}  =>  {dest_rel}  ({evt.device})")
                    elif evt.status == "duplicate":
                        self._cnt_dupes += 1
                        self._log("dupe", f"[DUP] {fname}  (duplicate quarantined)")
                    elif evt.status == "error":
                        self._cnt_errors += 1
                        self._log("error", f"[ERR] {fname}  {evt.error_msg}")
                    elif evt.status == "skipped":
                        self._log("info", f"[SKP] {fname}")

                    self._stat_vars["photos"].set(str(self._cnt_photos))
                    self._stat_vars["videos"].set(str(self._cnt_videos))
                    self._stat_vars["dupes"].set(str(self._cnt_dupes))
                    self._stat_vars["resumed"].set(str(self._cnt_resumed))
                    self._stat_vars["errors"].set(str(self._cnt_errors))

                elif evt.kind == EventKind.DONE:
                    s = evt.stats
                    self._prog_target_overall = 1.0
                    self._prog_target_current = 1.0
                    self._pulse_active = False
                    err_count = s.get("errors", 0)
                    icon = "✓" if not err_count else "⚠"
                    self._current_label.configure(
                        text=f"{icon}  Done",
                        text_color=("#2A6A2A", "#7AB648") if not err_count
                                   else ("#9A3010", "#E07050"))
                    elapsed = s.get("elapsed_sec", 0)
                    total   = s.get("total", 0)
                    speed   = f"{total/elapsed:.1f} files/s" if elapsed > 0 else ""
                    self._log("head",
                              f"Finished — moved/copied:{s.get('moved',0)}  "
                              f"dupes:{s.get('duplicates',0)}  "
                              f"errors:{s.get('errors',0)}  "
                              f"elapsed:{elapsed:.1f}s  {speed}")
                    self._btn_start.configure(state="normal")
                    self._btn_stop.configure(state="disabled")

                    # play completion sound — error tone if any errors, else complete
                    err_count = s.get("errors", 0)
                    self._play_sound("error" if err_count else "complete")

                    # system notification (if enabled and window is hidden/minimised)
                    if self._settings.get("notify_on_done", True):
                        self._maybe_notify(s)

                    # auto-save unresolved devices → no popup
                    if self._organizer:
                        self._auto_save_unresolved(
                            self._organizer._resolver.unresolved_devices)

        except queue.Empty:
            pass

        self.after(80, self._poll_events)

    # ── micro-animations (60 fps tick) ────────────────────────────────────────

    def _animate(self):
        """Smoothly interpolate progress bars toward their target values
        and pulse the current-file label while a run is in progress.

        Uses an ease-out curve (lerp at 18 % per frame) so motion feels
        organic and never jumpy, regardless of how fast events arrive.
        """
        try:
            # ── progress bars: ease toward target (lerp 18 % each frame) ──
            cur_o = self._prog_overall.get()
            cur_c = self._prog_current.get()
            tgt_o = self._prog_target_overall
            tgt_c = self._prog_target_current
            if abs(tgt_o - cur_o) > 0.0005:
                self._prog_overall.set(cur_o + (tgt_o - cur_o) * 0.18)
            elif cur_o != tgt_o:
                self._prog_overall.set(tgt_o)
            if abs(tgt_c - cur_c) > 0.0005:
                self._prog_current.set(cur_c + (tgt_c - cur_c) * 0.18)
            elif cur_c != tgt_c:
                self._prog_current.set(tgt_c)

            # ── current-file label pulse glow while running ──
            if self._pulse_active:
                import math
                self._pulse_phase = (self._pulse_phase + 0.12) % (2 * math.pi)
                # 0..1 sine wave → blend amber gold for warm pulse
                t = (math.sin(self._pulse_phase) + 1) * 0.5
                # interpolate text colour between muted gray and amber
                r = int(0x9A + (0xE0 - 0x9A) * t)
                g = int(0x88 + (0xA0 - 0x88) * t)
                b = int(0x70 + (0x30 - 0x70) * t)
                self._current_label.configure(
                    text_color=f"#{r:02X}{g:02X}{b:02X}")
        except Exception:
            pass

        self.after(16, self._animate)   # ~60 fps

    # ── log helpers ───────────────────────────────────────────────────────────

    def _log(self, tag: str, msg: str):
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _reset_ui(self):
        self._clear_log()
        self._prog_overall.set(0)
        self._prog_current.set(0)
        self._prog_target_overall = 0.0
        self._prog_target_current = 0.0
        self._pulse_active = False
        self._prog_label.configure(text="0 / 0")
        self._speed_label.configure(text="")
        self._current_label.configure(text="—",
                                      text_color=("gray50", "gray60"))
        for v in self._stat_vars.values():
            v.set("—")
        self._cnt_photos = self._cnt_videos = self._cnt_dupes = 0
        self._cnt_errors = self._cnt_resumed = 0

    @staticmethod
    def _rel(full_path: str) -> str:
        parts = Path(full_path).parts
        return str(Path(*parts[-4:])) if len(parts) >= 4 else full_path


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
