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

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtGui import QImage

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


# --------------------------------------------------------------------------- #
# Scan & thumbnail cache
# --------------------------------------------------------------------------- #

WALLPAPER_EXTS = frozenset(
    {".jpg", ".jpeg", ".jfif", ".png", ".bmp", ".webp", ".gif", ".avif"})


def scan_wallpapers(cfg: Config) -> list[Path]:
    """Every image under the wallpaper folder, sorted stably. Read-only."""
    root = Path(cfg.wallpaper_path)
    if not root.is_dir():
        return []
    it = root.rglob("*") if cfg.recursive else root.glob("*")
    files = [p for p in it if p.is_file() and p.suffix.lower() in WALLPAPER_EXTS]
    return sorted(files, key=lambda p: str(p).lower())


def thumb_key(p: Path) -> str:
    """sha1(abs_path | mtime_ns | size).

    Any rename, move, or edit yields a new key — which is what kills the
    reference implementation's stale-thumbnail and basename-collision bugs.
    """
    st = p.stat()
    raw = f"{p.resolve()}|{st.st_mtime_ns}|{st.st_size}"
    return hashlib.sha1(raw.encode("utf-8", "surrogatepass")).hexdigest() + ".jpg"


class _ThumbSignals(QObject):
    done = Signal(int)


class _ThumbWorker(QRunnable):
    def __init__(self, index: int, src: Path, dst: Path, signals: _ThumbSignals):
        super().__init__()
        self.index, self.src, self.dst, self.signals = index, src, dst, signals

    def run(self) -> None:
        try:
            img = QImage(str(self.src))
            if img.isNull():
                return
            scaled = img.scaledToHeight(THUMB_HEIGHT, Qt.SmoothTransformation)
            scaled.save(str(self.dst), "JPG", 85)
            self.signals.done.emit(self.index)
        except Exception:
            pass  # a broken image just keeps its placeholder


class ThumbCache(QObject):
    """One worker per image, pool width = cache_batch_size.

    Workers signal the tile index as each thumb lands, so the UI repaints exactly
    one tile — no polling, and no blank first run.
    """

    thumb_ready = Signal(int)

    def __init__(self, files: list[Path], batch: int):
        super().__init__()
        self.files = files
        self.keys = [thumb_key(p) for p in files]
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(max(1, batch))
        self._signals = _ThumbSignals()
        self._signals.done.connect(self.thumb_ready)

    def thumb_path(self, i: int) -> Path:
        return THUMB_DIR / self.keys[i]

    def start(self) -> None:
        THUMB_DIR.mkdir(parents=True, exist_ok=True)
        expected = set(self.keys)
        for stale in THUMB_DIR.iterdir():        # prune orphans (renamed/edited/deleted)
            if stale.name not in expected:
                try:
                    stale.unlink()
                except OSError:
                    pass
        for i, src in enumerate(self.files):
            dst = self.thumb_path(i)
            if not dst.exists():
                self.pool.start(_ThumbWorker(i, src, dst, self._signals))
