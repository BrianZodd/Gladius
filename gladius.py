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


def _apply_fit_mode(fit_mode: str) -> None:
    """The only registry write Gladius makes: the two fit-mode values."""
    style, tile = FIT_MODES.get(fit_mode, FIT_MODES["fill"])
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop",
                        0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, style)
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile)


def _spi_set(path: Path) -> bool:
    return bool(ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, str(path), SPIF_UPDATEINIFILE_SENDCHANGE))


def _transcode_to_png(path: Path) -> Path | None:
    img = QImage(str(path))
    if img.isNull():
        return None
    SET_DIR.mkdir(parents=True, exist_ok=True)
    out = SET_DIR / "current.png"
    return out if img.save(str(out), "PNG") else None


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
        return self.width() / self.cfg.number_of_pictures - 10

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
        tw, th = self.tile_w(), float(self.height())
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
            if pm and not pm.isNull():
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

        self.settings = None          # Stage 7 replaces with SettingsPane(self)

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
# CLI entry, single instance, --random
# --------------------------------------------------------------------------- #

def acquire_single_instance() -> bool:
    """False when an overlay is already open. The handle is intentionally leaked:
    the OS releases the mutex when this process exits."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW(None, False, "GladiusWallpaperPicker")
    return ctypes.get_last_error() != 183     # ERROR_ALREADY_EXISTS


def pick_random(files: list[Path], avoid: str) -> Path | None:
    if not files:
        return None
    pool = [p for p in files if str(p.resolve()) != avoid] or files
    return random.choice(pool)


def run_overlay(cfg: Config) -> int:
    app = QApplication([])
    files = scan_wallpapers(cfg)
    if not files:
        print(f"no wallpapers found in {cfg.wallpaper_path}", file=sys.stderr)
        return 1
    cache = ThumbCache(files, cfg.cache_batch_size)
    overlay = Overlay(cfg, files, cache)
    overlay.present()
    cache.start()          # after show: placeholders paint first, thumbs stream in
    return app.exec()


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
        from PySide6.QtGui import QGuiApplication   # transcode path needs a Qt app
        _app = QGuiApplication([])
        choice = pick_random(scan_wallpapers(cfg), get_current_wallpaper())
        if choice is None:
            print(f"no wallpapers found in {cfg.wallpaper_path}", file=sys.stderr)
            return 1
        return 0 if select_wallpaper(choice, cfg) else 1

    if not acquire_single_instance():
        return 0                              # an overlay is already open — do nothing
    cfg._windowed = args.windowed             # debug flag rides on the instance
    return run_overlay(cfg)


if __name__ == "__main__":
    sys.exit(main())
