"""Gladius — keyboard-driven wallpaper picker overlay for Windows.

A faithful PySide6 port of hyprquickpaper (behavior parity, original code).
MIT licensed. https://github.com/iamsurjog/hyprquickpaper is the reference.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import random
import subprocess
import sys
import winreg
from ctypes import wintypes
from dataclasses import dataclass, asdict, fields
from pathlib import Path

CONFIG_DIR = Path(os.environ["APPDATA"]) / "Gladius"
CONFIG_PATH = CONFIG_DIR / "config.json"
DATA_DIR = Path(os.environ["LOCALAPPDATA"]) / "Gladius"
THUMB_DIR = DATA_DIR / "thumbs"
SET_DIR = DATA_DIR / "set"
THUMB_HEIGHT = 500


# --------------------------------------------------------------------------- #
# Config & paths
# --------------------------------------------------------------------------- #

def pictures_dir() -> Path:
    """The real Pictures folder, via SHGetKnownFolderPath.

    Not %USERPROFILE%\\Pictures: user folders can be redirected elsewhere, and
    only the known-folder API reports where they actually are.
    """
    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    guid = _GUID()
    ctypes.oledll.ole32.CLSIDFromString(
        "{33E28130-4E1E-4676-835A-98395C3BC3BB}", ctypes.byref(guid))  # FOLDERID_Pictures
    out = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(out)) != 0:
        return Path.home() / "Pictures"  # S_OK is 0; anything else → sane fallback
    try:
        return Path(out.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out)


@dataclass
class Config:
    wallpaper_path: str = ""          # "" → resolved to <Pictures>\Wallpapers at load
    recursive: bool = True
    number_of_pictures: int = 7
    border_color: str = "#C27B63"
    backdrop: str = "dim"             # "dim" | "acrylic"
    dim_opacity: float = 0.7
    shear: bool = True
    fit_mode: str = "fill"            # key of FIT_MODES
    cache_batch_size: int = 8
    on_select_command: str | None = None

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        if CONFIG_PATH.exists():
            try:
                raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                raw = {}
            known = {f.name for f in fields(cls)}
            for k, v in raw.items():
                if k in known:
                    setattr(cfg, k, v)
        if not cfg.wallpaper_path:
            cfg.wallpaper_path = str(pictures_dir() / "Wallpapers")
        cfg.number_of_pictures = max(3, min(15, int(cfg.number_of_pictures)))
        cfg.dim_opacity = max(0.0, min(1.0, float(cfg.dim_opacity)))
        if cfg.backdrop not in ("dim", "acrylic"):
            cfg.backdrop = "dim"
        if not CONFIG_PATH.exists():
            cfg.save()                # first run: materialize defaults for the user to edit
        return cfg

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
