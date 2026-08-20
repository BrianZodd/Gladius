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

from PySide6.QtCore import (QEasingCurve, QObject, QPointF, QRectF, QRunnable,
                            QThreadPool, Qt, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QCursor, QGuiApplication, QImage, QKeyEvent,
                           QPainter, QPen, QPixmap)
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

def _app_dir(var: str, fallback: str) -> Path:
    """%APPDATA% / %LOCALAPPDATA%, with a fallback for environments that
    don't set them (services, stripped shells, portable setups)."""
    root = os.environ.get(var)
    return Path(root) if root else Path.home() / "AppData" / fallback


CONFIG_DIR = _app_dir("APPDATA", "Roaming") / "Gladius"
CONFIG_PATH = CONFIG_DIR / "config.json"
DATA_DIR = _app_dir("LOCALAPPDATA", "Local") / "Gladius"
THUMB_DIR = DATA_DIR / "thumbs"
SET_DIR = DATA_DIR / "set"
THUMB_HEIGHT = 500          # floor; thumb_height() scales up for bigger displays


# --------------------------------------------------------------------------- #
# Config & paths
# --------------------------------------------------------------------------- #

def pictures_dir() -> Path:
    """The real Pictures folder, via SHGetKnownFolderPath.

    Not %USERPROFILE%\\Pictures: user folders can be redirected elsewhere, and
    only the known-folder API reports where they actually are. Any failure falls
    back to the conventional location rather than taking the app down.
    """
    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    try:
        guid = _GUID()
        ctypes.oledll.ole32.CLSIDFromString(
            "{33E28130-4E1E-4676-835A-98395C3BC3BB}", ctypes.byref(guid))  # FOLDERID_Pictures
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(out)) != 0:
            return Path.home() / "Pictures"  # S_OK is 0; anything else → fallback
        try:
            return Path(out.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(out)
    except Exception:
        return Path.home() / "Pictures"


def _as_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _as_number(value, caster, default, low, high):
    try:
        return max(low, min(high, caster(value)))
    except (TypeError, ValueError):
        return default


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
        cfg._sanitize()
        if not CONFIG_PATH.exists():
            cfg.save()                # first run: materialize defaults for the user to edit
        return cfg

    def _sanitize(self) -> None:
        """Coerce every field to something usable.

        The config is a hand-editable file and Gladius is launched by a hotkey
        with no console, so a bad value must degrade to the default rather than
        surface as a silent non-launch.
        """
        d = Config()
        if not isinstance(self.wallpaper_path, str) or not self.wallpaper_path:
            self.wallpaper_path = str(pictures_dir() / "Wallpapers")
        self.recursive = _as_bool(self.recursive, d.recursive)
        self.shear = _as_bool(self.shear, d.shear)
        self.number_of_pictures = _as_number(
            self.number_of_pictures, int, d.number_of_pictures, 3, 15)
        self.dim_opacity = _as_number(self.dim_opacity, float, d.dim_opacity, 0.0, 1.0)
        self.cache_batch_size = _as_number(
            self.cache_batch_size, int, d.cache_batch_size, 1, 64)
        if self.backdrop not in ("dim", "acrylic"):
            self.backdrop = d.backdrop
        if self.fit_mode not in FIT_MODES:
            self.fit_mode = d.fit_mode
        if not QColor.isValidColorName(str(self.border_color)):
            self.border_color = d.border_color
        if not isinstance(self.on_select_command, str) or not self.on_select_command:
            self.on_select_command = None

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


def thumb_height() -> int:
    """Thumbnail height in device pixels, sized for the largest attached screen.

    A fixed height would upscale (and look soft) on a 4K or high-DPI display, so
    it tracks the display and is folded into the cache key below.
    """
    try:
        tallest = max(int(s.geometry().height() * s.devicePixelRatio())
                      for s in QGuiApplication.screens())
    except (ValueError, RuntimeError, AttributeError):
        return THUMB_HEIGHT            # no Qt app yet — the floor is fine
    return max(THUMB_HEIGHT, min(1600, int(tallest * 0.6)))


def thumb_key(p: Path, height: int = THUMB_HEIGHT) -> str:
    """sha1(abs_path | mtime_ns | size | height).

    Any rename, move, or edit yields a new key — which is what kills the
    reference implementation's stale-thumbnail and basename-collision bugs.
    Height is included so a different display resolution gets its own entries
    instead of reusing thumbnails that are too small for it.
    """
    try:
        st = p.stat()
        raw = f"{p.resolve()}|{st.st_mtime_ns}|{st.st_size}|{height}"
    except OSError:                    # vanished between scan and cache build
        raw = f"{p}|missing|{height}"
    return hashlib.sha1(raw.encode("utf-8", "surrogatepass")).hexdigest() + ".jpg"


class _ThumbSignals(QObject):
    done = Signal(int)


class _ThumbWorker(QRunnable):
    def __init__(self, index: int, src: Path, dst: Path, signals: _ThumbSignals,
                 height: int = THUMB_HEIGHT):
        super().__init__()
        self.index, self.src, self.dst, self.signals = index, src, dst, signals
        self.height = height

    def run(self) -> None:
        try:
            img = QImage(str(self.src))
            if img.isNull():
                return
            scaled = img.scaledToHeight(self.height, Qt.SmoothTransformation)
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
        self.height = thumb_height()
        self.keys = [thumb_key(p, self.height) for p in files]
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(max(1, batch))
        self._signals = _ThumbSignals()
        self._signals.done.connect(self.thumb_ready)

    def thumb_path(self, i: int) -> Path:
        return THUMB_DIR / self.keys[i]

    def start(self) -> None:
        try:
            THUMB_DIR.mkdir(parents=True, exist_ok=True)
            expected = set(self.keys)
            for stale in THUMB_DIR.iterdir():    # prune orphans (renamed/edited/deleted)
                if stale.name not in expected:
                    try:
                        stale.unlink()
                    except OSError:
                        pass
        except OSError:
            return                               # unwritable cache dir → placeholders only
        for i, src in enumerate(self.files):
            dst = self.thumb_path(i)
            if not dst.exists():
                self.pool.start(_ThumbWorker(i, src, dst, self._signals, self.height))


# --------------------------------------------------------------------------- #
# Setting the wallpaper (Win32)
# --------------------------------------------------------------------------- #

FIT_MODES = {
    "fill":    ("10", "0"),
    "fit":     ("6",  "0"),
    "span":    ("22", "0"),
    "stretch": ("2",  "0"),
    "center":  ("0",  "0"),
    "tile":    ("0",  "1"),
}
DIRECT_EXTS = frozenset({".jpg", ".jpeg", ".jfif", ".png", ".bmp"})
SPI_SETDESKWALLPAPER = 0x0014
SPI_GETDESKWALLPAPER = 0x0073
SPIF_UPDATEINIFILE_SENDCHANGE = 0x3


def _apply_fit_mode(fit_mode: str) -> bool:
    """The only registry write Gladius makes: the two fit-mode values.

    A locked-down or policy-restricted registry costs the fit mode, not the
    wallpaper — the caller sets the image either way.
    """
    style, tile = FIT_MODES.get(fit_mode, FIT_MODES["fill"])
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop",
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, style)
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile)
        return True
    except OSError:
        return False


def _spi_set(path: Path) -> bool:
    """Hand the wallpaper path to Windows — always fully resolved.

    Explorer reads the file itself, from outside this process. If Python is
    running under MSIX filesystem redirection (Microsoft Store Python, or any
    packaged host), a path under %LOCALAPPDATA% is redirected to a
    package-private store that Explorer cannot see: the call reports success and
    the desktop silently keeps the old wallpaper. Resolving yields the real
    backing path, which works either way. Verified both ways on a redirected
    host — identical bytes, ignored unresolved, applied resolved.
    """
    try:
        target = path.resolve()
    except OSError:
        target = path
    return bool(ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, str(target), SPIF_UPDATEINIFILE_SENDCHANGE))


def _transcode_to_png(path: Path) -> Path | None:
    try:
        img = QImage(str(path))
        if img.isNull():
            return None
        SET_DIR.mkdir(parents=True, exist_ok=True)
        out = SET_DIR / "current.png"
        return out if img.save(str(out), "PNG") else None
    except OSError:
        return None


def set_wallpaper(path: Path, fit_mode: str) -> bool:
    """Set the desktop wallpaper, transcoding formats Windows can't read itself.

    QImage reads webp/avif/gif fine, but SystemParametersInfoW does not — those
    (and any direct attempt that fails) go through a PNG in the scratch dir.
    """
    _apply_fit_mode(fit_mode)
    p = path.resolve()
    if p.suffix.lower() in DIRECT_EXTS and _spi_set(p):
        return True
    out = _transcode_to_png(p)
    return _spi_set(out) if out else False


def get_current_wallpaper() -> str:
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETDESKWALLPAPER, 260, buf, 0)
    return buf.value


def build_select_command(template: str, path: Path) -> str:
    return template.replace("{path}", str(path.resolve()))


def select_wallpaper(path: Path, cfg: Config) -> bool:
    if cfg.on_select_command:
        subprocess.Popen(build_select_command(cfg.on_select_command, path), shell=True,
                         creationflags=subprocess.CREATE_NO_WINDOW
                                     | subprocess.DETACHED_PROCESS)
        return True                      # parity with commands.sh: fire-and-forget
    return set_wallpaper(path, cfg.fit_mode)


# --------------------------------------------------------------------------- #
# StripView — the horizontal strip of tiles (one widget, one paintEvent)
# --------------------------------------------------------------------------- #

SPACING = 4
SHEAR_X = -0.25          # the reference implementation's parallelogram lean
DRAG_THRESHOLD = 5       # px of motion that turns a click into a drag


class StripView(QWidget):
    index_changed = Signal(int)
    picked = Signal(int)

    def __init__(self, files, cache, cfg, parent=None):
        super().__init__(parent)
        self.files, self.cache, self.cfg = files, cache, cfg
        self.index = 0
        self.content_x = 0.0
        self._pixmaps: dict[int, QPixmap] = {}
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(100)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self._drag_origin: QPointF | None = None
        self._drag_start_x = 0.0
        self._dragging = False
        self.setFocusPolicy(Qt.NoFocus)      # keys are handled by the overlay
        cache.thumb_ready.connect(self.on_thumb_ready)

    # --- geometry ---
    def tile_w(self) -> float:
        # never zero or negative: the widget can be painted mid-layout, and a
        # narrow window with many tiles would otherwise divide by zero below
        return max(1.0, self.width() / max(1, self.cfg.number_of_pictures) - 10)

    def step(self) -> float:
        return self.tile_w() + SPACING

    def content_width(self) -> float:
        return len(self.files) * self.step() - SPACING

    def _clamp_x(self, x: float) -> float:
        return max(0.0, min(x, self.content_width() - self.width()))

    def _clamp_index(self, i: int) -> int:
        return max(0, min(i, len(self.files) - 1))

    def _ensure_visible(self, i: int) -> None:
        step = self.step()
        item_start = i * step
        item_end = item_start + self.tile_w() + 20
        if item_start < self.content_x:
            self._animate_to(self._clamp_x(item_start))
        elif item_end > self.content_x + self.width():
            self._animate_to(self._clamp_x(item_start - (self.width() - step)))

    def _animate_to(self, x: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self.content_x)
        self._anim.setEndValue(x)
        self._anim.start()

    def _on_anim(self, v) -> None:
        self.content_x = float(v)
        self.update()

    # --- selection API (the overlay calls these) ---
    def set_index(self, i: int) -> None:
        self.index = self._clamp_index(i)
        self._ensure_visible(self.index)
        self.index_changed.emit(self.index)
        self.update()

    def move(self, delta: int) -> None:
        self.set_index(self.index + delta)

    def page(self, delta: int) -> None:
        self.set_index(self.index + delta * self.cfg.number_of_pictures)

    def relayout(self) -> None:
        self.content_x = self._clamp_x(self.content_x)
        self._ensure_visible(self.index)
        self.update()

    def on_thumb_ready(self, i: int) -> None:
        self._pixmaps.pop(i, None)           # drop the remembered placeholder-miss
        self.update()

    # --- painting ---
    def _pixmap(self, i: int) -> QPixmap | None:
        pm = self._pixmaps.get(i)
        if pm is not None:
            return pm or None                # cached null → still loading
        path = self.cache.thumb_path(i)
        if path.exists():
            pm = QPixmap(str(path))
            self._pixmaps[i] = pm
            return pm
        self._pixmaps[i] = QPixmap()         # remember the miss until thumb_ready
        return None

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        tw, th = self.tile_w(), float(max(1, self.height()))
        step = self.step()
        first = max(0, int(self.content_x // step) - 1)
        last = min(len(self.files) - 1,
                   int((self.content_x + self.width()) // step) + 1)
        for i in range(first, last + 1):
            x = i * step - self.content_x
            p.save()
            p.translate(x, 0)
            if self.cfg.shear:
                p.shear(SHEAR_X, 0)
            p.setClipRect(QRectF(0, 0, tw, th))
            pm = self._pixmap(i)
            if pm and not pm.isNull() and pm.width() > 0 and pm.height() > 0:
                # PreserveAspectCrop: source rect matches tile aspect, centered
                tile_ar = tw / th
                src_ar = pm.width() / pm.height()
                if src_ar > tile_ar:
                    sh = pm.height()
                    sw = sh * tile_ar
                else:
                    sw = pm.width()
                    sh = sw / tile_ar
                src = QRectF((pm.width() - sw) / 2, (pm.height() - sh) / 2, sw, sh)
                p.drawPixmap(QRectF(0, 0, tw, th), pm, src)
            else:
                p.fillRect(QRectF(0, 0, tw, th), QColor(255, 255, 255, 18))
                p.setPen(QColor(self.cfg.border_color))
                p.drawText(QRectF(0, 0, tw, th), Qt.AlignCenter, "Loading…")
            if i == self.index:
                pen = QPen(QColor(self.cfg.border_color))
                pen.setWidth(4)
                p.setPen(pen)
                p.drawRect(QRectF(2, 2, tw - 4, th - 4))
            p.restore()
        p.end()

    # --- mouse (parity: wheel scrolls, drag scrolls, click selects) ---
    def wheelEvent(self, ev) -> None:
        self._anim.stop()
        self.content_x = self._clamp_x(self.content_x - ev.angleDelta().y() * 2)
        self.update()

    def mousePressEvent(self, ev) -> None:
        self._drag_origin = ev.position()
        self._drag_start_x = self.content_x
        self._dragging = False

    def mouseMoveEvent(self, ev) -> None:
        if self._drag_origin is None:
            return
        dx = ev.position().x() - self._drag_origin.x()
        if abs(dx) > DRAG_THRESHOLD:
            self._dragging = True
        if self._dragging:
            self._anim.stop()
            self.content_x = self._clamp_x(self._drag_start_x - dx)
            self.update()

    def mouseReleaseEvent(self, ev) -> None:
        if self._drag_origin is not None and not self._dragging:
            i = int((self.content_x + ev.position().x()) // self.step())
            if 0 <= i < len(self.files):
                self.set_index(i)
                self.picked.emit(i)
        self._drag_origin = None
        self._dragging = False


# --------------------------------------------------------------------------- #
# Overlay window
# --------------------------------------------------------------------------- #

ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
WCA_ACCENT_POLICY = 19
ACRYLIC_TINT = 0x30000000        # AABBGGRR — light enough to leave the blur visible


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class _WINCOMPATTRDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t)]


def enable_acrylic(hwnd: int) -> bool:
    """Turn on Windows' acrylic blur-behind for this window.

    Uses SetWindowCompositionAttribute — the documented DWM system-backdrop
    attribute reports success but paints a flat opaque panel on a frameless
    layered window, so it is deliberately not used (see RESEARCH-notes.md, R1).
    Qt's WA_TranslucentBackground stays on. Returns False on any failure, and the
    overlay silently falls back to the dim backdrop.
    """
    try:
        fn = ctypes.windll.user32.SetWindowCompositionAttribute
        fn.argtypes = [wintypes.HWND, ctypes.POINTER(_WINCOMPATTRDATA)]
        fn.restype = ctypes.c_int
        accent = _ACCENT_POLICY(ACCENT_ENABLE_ACRYLICBLURBEHIND, 2, ACRYLIC_TINT, 0)
        data = _WINCOMPATTRDATA(WCA_ACCENT_POLICY,
                                ctypes.cast(ctypes.byref(accent), ctypes.c_void_p),
                                ctypes.sizeof(accent))
        return bool(fn(wintypes.HWND(hwnd), ctypes.byref(data)))
    except Exception:
        return False


class Overlay(QWidget):
    def __init__(self, cfg: Config, files: list[Path], cache: ThumbCache):
        # Qt.Tool ⇒ WS_EX_TOOLWINDOW, which is what keeps tiling window managers
        # from ever managing this window (verified under komorebi — R2).
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        super().__init__(None, flags)
        self.cfg, self.files, self.cache = cfg, files, cache
        self.setWindowTitle("gladius")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._acrylic_on = False

        self.strip = StripView(files, cache, cfg, self)
        self.footer = QLabel(self)
        self.footer.setStyleSheet(
            "color: rgba(255,255,255,200); font-family: 'Segoe UI'; font-size: 15px;")
        self.footer.setAlignment(Qt.AlignCenter)

        self.settings = SettingsPane(self)   # created last ⇒ stacks above the strip

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(2)
        lay.addWidget(self.strip, stretch=5)   # strip ≈ half the screen height
        lay.addSpacing(12)
        lay.addWidget(self.footer)
        lay.addStretch(2)

        self.strip.index_changed.connect(self._update_footer)
        self.strip.picked.connect(self._select_and_exit)

        # start on the currently-set wallpaper when it's in the list (SPEC §3)
        current = get_current_wallpaper()
        for i, f in enumerate(files):
            if str(f.resolve()) == current:
                self.strip.index = i
                break
        self._update_footer(self.strip.index)

    # --- lifecycle ---
    def present(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) \
                 or QGuiApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        if getattr(self.cfg, "_windowed", False):        # debug: normal window
            self.setWindowFlags(Qt.WindowStaysOnTopHint)
            self.resize(1600, 500)
            self.show()
        else:
            self.showFullScreen()
        self.raise_()
        self.activateWindow()
        if self.cfg.backdrop == "acrylic":
            self._acrylic_on = enable_acrylic(int(self.winId()))
        self.strip.set_index(self.strip.index)           # scroll selection into view

    def apply_setting(self, key: str) -> None:           # Stage 7 calls this per change
        if key == "backdrop":
            self._acrylic_on = (self.cfg.backdrop == "acrylic"
                                and enable_acrylic(int(self.winId())))
        elif key == "number_of_pictures":
            self.strip.relayout()
        self.cfg.save()
        self.update()
        self.strip.update()

    def _update_footer(self, i: int) -> None:
        if self.files:
            self.footer.setText(
                f"{self.files[i].name}      {i + 1} / {len(self.files)}")

    def _select_and_exit(self, i: int) -> None:
        select_wallpaper(self.files[i], self.cfg)
        QApplication.quit()

    # --- painting: the backdrop ---
    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        if self._acrylic_on:
            p.fillRect(self.rect(), QColor(0, 0, 0, 60))   # light tint over the blur
        else:
            p.fillRect(self.rect(),
                       QColor(0, 0, 0, int(self.cfg.dim_opacity * 255)))
        p.end()

    # --- keys (SPEC §3 table) ---
    def keyPressEvent(self, ev: QKeyEvent) -> None:
        if self.settings is not None and self.settings.isVisible():
            self.settings.handle_key(ev)                 # Esc/S close it there
            return
        k = ev.key()
        if k in (Qt.Key_J, Qt.Key_Right):
            self.strip.move(1)
        elif k in (Qt.Key_K, Qt.Key_Left):
            self.strip.move(-1)
        elif k == Qt.Key_D:
            self.strip.page(1)
        elif k == Qt.Key_U:
            self.strip.page(-1)
        elif k in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self._select_and_exit(self.strip.index)
        elif k == Qt.Key_S:
            if self.settings is not None:
                self.settings.toggle()
        elif k == Qt.Key_Escape:
            QApplication.quit()


# --------------------------------------------------------------------------- #
# Settings pane
# --------------------------------------------------------------------------- #

BORDER_PALETTE = ["#C27B63", "#E06C75", "#98C379", "#E5C07B",
                  "#61AFEF", "#C678DD", "#56B6C2", "#FFFFFF"]

SETTINGS_ROWS = [
    ("backdrop",           "Backdrop",       ["dim", "acrylic"]),
    ("dim_opacity",        "Dim opacity",    [0.5, 0.6, 0.7, 0.8, 0.9]),
    ("shear",              "Shear tiles",    [True, False]),
    ("border_color",       "Border color",   BORDER_PALETTE),
    ("fit_mode",           "Fit mode",       list(FIT_MODES.keys())),
    ("number_of_pictures", "Visible tiles",  list(range(3, 16))),
]


class SettingsPane(QWidget):
    def __init__(self, overlay: "Overlay"):
        super().__init__(overlay)
        self.overlay = overlay
        self.row = 0
        self.setVisible(False)

    def toggle(self) -> None:
        if not self.isVisible():
            w, h = 440, 40 + 44 * len(SETTINGS_ROWS)
            self.setGeometry((self.overlay.width() - w) // 2,
                             (self.overlay.height() - h) // 2, w, h)
        self.setVisible(not self.isVisible())
        self.overlay.update()

    def _cycle(self, key: str, values: list, delta: int) -> None:
        cur = getattr(self.overlay.cfg, key)
        try:
            i = values.index(cur)
        except ValueError:
            i = 0 if delta > 0 else len(values) - 1   # custom value → enter at the edge
            delta = 0
        setattr(self.overlay.cfg, key, values[(i + delta) % len(values)])
        self.overlay.apply_setting(key)
        self.update()

    def handle_key(self, ev: QKeyEvent) -> None:
        k = ev.key()
        key, _, values = SETTINGS_ROWS[self.row]
        if k in (Qt.Key_J, Qt.Key_Down):
            self.row = (self.row + 1) % len(SETTINGS_ROWS)
        elif k in (Qt.Key_K, Qt.Key_Up):
            self.row = (self.row - 1) % len(SETTINGS_ROWS)
        elif k in (Qt.Key_L, Qt.Key_Right):
            self._cycle(key, values, +1)
        elif k in (Qt.Key_H, Qt.Key_Left):
            self._cycle(key, values, -1)
        elif k in (Qt.Key_Escape, Qt.Key_S):
            self.toggle()
        self.update()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(20, 20, 20, 235))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 10, 10)
        p.setFont(self.font())
        y = 20
        for r, (key, label, _values) in enumerate(SETTINGS_ROWS):
            val = getattr(self.overlay.cfg, key)
            shown = {True: "on", False: "off"}.get(val, str(val))
            if r == self.row:
                p.setBrush(QColor(255, 255, 255, 25))
                p.drawRoundedRect(QRectF(10, y - 4, self.width() - 20, 36), 6, 6)
            p.setPen(QColor(255, 255, 255, 220))
            p.drawText(QRectF(24, y, 250, 30), Qt.AlignVCenter, label)
            if key == "border_color":
                p.setBrush(QColor(str(val)))
                p.setPen(QColor(255, 255, 255, 90))
                p.drawRect(QRectF(self.width() - 120, y + 4, 22, 22))
                p.setPen(QColor(255, 255, 255, 220))
                p.drawText(QRectF(self.width() - 90, y, 70, 30),
                           Qt.AlignVCenter, str(val))
            else:
                p.setPen(QColor(255, 255, 255, 220))
                p.drawText(QRectF(self.width() - 190, y, 166, 30),
                           Qt.AlignVCenter | Qt.AlignRight, f"‹ {shown} ›")
            p.setPen(Qt.NoPen)
            y += 44
        p.end()


# --------------------------------------------------------------------------- #
# CLI entry, single instance, --random
# --------------------------------------------------------------------------- #

def report(message: str, dialog: bool) -> None:
    """Surface a startup failure.

    Launched from a hotkey via pythonw there is no console, so stderr alone
    would make a failure look like the hotkey doing nothing. `dialog` is False
    for --random, which may run unattended from a scheduled task where a modal
    box would block forever.
    """
    print(message, file=sys.stderr)
    if not dialog:
        return
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "Gladius", message)
    except Exception:
        pass


def acquire_single_instance() -> bool:
    """False when an overlay is already open. The handle is intentionally leaked:
    the OS releases the mutex when this process exits."""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW(None, False, "GladiusWallpaperPicker")
        return ctypes.get_last_error() != 183     # ERROR_ALREADY_EXISTS
    except Exception:
        return True                               # can't tell → let it run


def pick_random(files: list[Path], avoid: str) -> Path | None:
    if not files:
        return None
    pool = [p for p in files if str(p.resolve()) != avoid] or files
    return random.choice(pool)


def run_overlay(cfg: Config) -> int:
    app = QApplication([])
    files = scan_wallpapers(cfg)
    if not files:
        report(_no_wallpapers_message(cfg), dialog=True)
        return 1
    cache = ThumbCache(files, cfg.cache_batch_size)
    overlay = Overlay(cfg, files, cache)
    overlay.present()
    cache.start()          # after show: placeholders paint first, thumbs stream in
    return app.exec()


def _no_wallpapers_message(cfg: Config) -> str:
    return (f"No images found in:\n{cfg.wallpaper_path}\n\n"
            f"Point 'wallpaper_path' at your wallpaper folder in:\n{CONFIG_PATH}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gladius",
                                 description="Keyboard-driven wallpaper picker overlay.")
    ap.add_argument("--random", action="store_true",
                    help="set a random wallpaper and exit (no UI)")
    ap.add_argument("--config", action="store_true",
                    help="print the config file path and exit")
    ap.add_argument("--windowed", action="store_true", help=argparse.SUPPRESS)  # debug
    args = ap.parse_args(argv)

    if args.config:
        print(CONFIG_PATH)
        return 0

    cfg = Config.load()

    if args.random:
        _app = QGuiApplication([])                 # transcode path needs a Qt app
        choice = pick_random(scan_wallpapers(cfg), get_current_wallpaper())
        if choice is None:
            report(_no_wallpapers_message(cfg), dialog=False)   # may be unattended
            return 1
        return 0 if select_wallpaper(choice, cfg) else 1

    if not acquire_single_instance():
        return 0                              # an overlay is already open — do nothing
    cfg._windowed = args.windowed             # debug flag rides on the instance
    return run_overlay(cfg)


if __name__ == "__main__":
    sys.exit(main())
