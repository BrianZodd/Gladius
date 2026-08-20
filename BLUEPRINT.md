# ⏳ TEMPORARY — DELETE WHEN: all stages shipped + live acceptance passed → essence to ROADMAP/DECISIONS, keepable detail to ARCHIVE

# Gladius v1 — Execution Blueprint (BIG-PROJECT)

**Goal**: build Gladius v1 exactly as specified in `SPEC.md` — a PySide6 wallpaper-picker
overlay for Windows, faithful port of hyprquickpaper — through live acceptance on this
machine.

**Approach**: one Python file (`gladius.py`) built bottom-up in stages: pure logic first
(config, scan, cache, setter — each TDD'd with stdlib `unittest`), then the GUI (strip →
overlay → settings pane), then system integration (whkd, komorebi) and the live acceptance
run. Two runtime unknowns are spiked in Stage R; their findings refine Stages 6–8 only.

**Executor protocol**:
- Work stages in order (Stage R may run any time before Stage 6). One commit per stage
  minimum, message `stage N: <summary>`.
- TDD where a unit is testable: write the failing test in `test_gladius.py`, run
  `python -m unittest test_gladius -v` to see it fail, implement minimally, see green,
  commit. GUI stages verify by running the app (`--windowed` debug flag, Stage 5).
- After each stage, update the one live line in `ROADMAP.md` → Current focus:
  `Blueprint: BLUEPRINT.md — stage N/9 done, next: Stage N+1`.
- Read `CLAUDE.md` first (invariants). Key ones inherited by every stage, verbatim:
  1. Nothing machine-specific is committed — user config in `%APPDATA%\Gladius\`, generated
     files in `%LOCALAPPDATA%\Gladius\`; the repo must work verbatim for a stranger.
  2. Single-file app, single dependency: `gladius.py` + stdlib + PySide6.
  3. No code reuse from hyprquickpaper (unlicensed) — behavior parity only.
  4. The wallpaper folder is read-only to Gladius.
  5. Registry writes limited to `HKCU\Control Panel\Desktop` → `WallpaperStyle`,
     `TileWallpaper`.
  6. "Done" = the live acceptance run (Stage 8) passed under running komorebi.

**Non-goals (do not build, even if tempting)**: live wallpaper preview while scrolling ·
per-monitor wallpapers (`IDesktopWallpaper` COM) · grid layout · animated set-transitions ·
tray/daemon mode · config-file hot-reload · packaging (PyInstaller/PyPI). All parked in
ROADMAP.md → Active to-dos.

**File map (created by this blueprint)**:
| Path | Owner stage | Responsibility |
|---|---|---|
| `.gitignore`, `requirements.txt` | 0 | hygiene |
| `RESEARCH-notes.md` (⏳ temp) | R | spike findings |
| `gladius.py` | 1–7 | the entire app |
| `test_gladius.py` (repo root) | 1–4 | stdlib-unittest suite for the pure logic |
| `LICENSE`, README completion | 9 | public readiness |

---

## Stage 0 — Repo & environment

**Files**: Create `.gitignore`, `requirements.txt`. No test file.

**Steps**:
- [ ] Repo is already initialized with the planning commit (docs + SPEC + BLUEPRINT); this
      stage only adds its two files. Repo stays private/local; no remote yet.
- [ ] Create `.gitignore`:
      ```
      __pycache__/
      *.pyc
      .venv/
      ```
- [ ] Create `requirements.txt`:
      ```
      PySide6
      ```
- [ ] `pip install PySide6` — then record the installed version:
      `pip show PySide6 | Select-String Version` → pin it: rewrite `requirements.txt` as
      e.g. `PySide6>=6.9` (major.minor actually installed).
- [ ] Locate interpreter paths for later stages (record in RESEARCH-notes.md when it exists,
      or a scratch note): `(Get-Command python).Source` and `(Get-Command pythonw).Source`.
- [ ] Commit everything currently in the folder (six docs + SPEC.md + BLUEPRINT.md +
      the two new files): `git add -A; git commit -m "stage 0: repo init, docs scaffold, deps"`.

**Verification**: `git log --oneline` shows one commit; `python -c "import PySide6; print(PySide6.__version__)"` prints a version.

---

## Stage R — Research spikes (refines Stages 6 & 8; gates nothing before them)

Findings land in `RESEARCH-notes.md` at repo root with header:
`# ⏳ TEMPORARY — DELETE WHEN: BLUEPRINT.md dies (findings distilled into DECISIONS.md)`.

### R1 — Acrylic blur on a frameless translucent Qt window (refines Stage 6)

Write throwaway `spike_acrylic.py` (delete after; do not commit) — a frameless,
translucent, 800×600 always-on-top window that tries, in order:

- **Attempt A — documented Win11 API**: after `show()`,
  ```python
  import ctypes
  hwnd = int(win.winId())
  DWMWA_SYSTEMBACKDROP_TYPE = 38
  DWMSBT_TRANSIENTWINDOW = 3  # acrylic
  ctypes.windll.dwmapi.DwmSetWindowAttribute(
      hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
      ctypes.byref(ctypes.c_int(DWMSBT_TRANSIENTWINDOW)), 4)
  ```
- **Attempt B — undocumented but battle-tested**: `SetWindowCompositionAttribute` with an
  ACCENT_POLICY:
  ```python
  import ctypes
  from ctypes import wintypes

  class ACCENT_POLICY(ctypes.Structure):
      _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                  ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]

  class WINCOMPATTRDATA(ctypes.Structure):
      _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p),
                  ("SizeOfData", ctypes.c_size_t)]

  accent = ACCENT_POLICY(4, 2, 0x99000000, 0)  # 4 = ACCENT_ENABLE_ACRYLICBLURBEHIND, AABBGGRR tint
  data = WINCOMPATTRDATA(19, ctypes.cast(ctypes.byref(accent), ctypes.c_void_p),
                         ctypes.sizeof(accent))  # 19 = WCA_ACCENT_POLICY
  ctypes.windll.user32.SetWindowCompositionAttribute(int(win.winId()), ctypes.byref(data))
  ```

**Decide**: whichever attempt shows real blur-behind without artifacts becomes the body of
`enable_acrylic(hwnd) -> bool` in Stage 6 (return `False` on any exception or if the call
reports failure). If **both** fail or artifact: record it, and Stage 6 ships dim-only with
the settings row still present but annotated "(acrylic unavailable on this system)" at
runtime by `enable_acrylic` returning False → overlay silently uses dim. Note whether
`WA_TranslucentBackground` had to be dropped for blur to render (known interaction) — if so,
Stage 6's acrylic path uses an opaque black base widget instead of translucency.

### R2 — Does `Qt.Tool` keep komorebi's hands off? (refines Stage 6 window flags + Stage 8 fallback)

With komorebi running normally, write throwaway `spike_tool.py`: fullscreen frameless window
with flags `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`, dim-black
translucent background, closes on any key. Launch it from a terminal.

**Check**: window appears fullscreen above tiled windows; komorebi does NOT resize/retile it
or shuffle other windows; it takes keyboard focus (keypress closes it); after close, focus
returns to the previously focused window.

**Decide**: pass → Stage 6 keeps `Qt.Tool`, Stage 8 skips the applications.json rule.
Fail → Stage 8 adds the float rule (procedure written there), and if komorebi *still*
interferes, escalate to `WS_EX_NOACTIVATE`-free manual style set via
`SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW)` (GWL_EXSTYLE = -20,
WS_EX_TOOLWINDOW = 0x80) after `show()` — record which combination worked.

**Verification (Stage R)**: `RESEARCH-notes.md` exists with a dated verdict line per spike:
which acrylic attempt (A/B/none) and which komorebi strategy (Tool-only / +rule / +manual
style). Commit: `stage R: spike findings`.

---

## Stage 1 — Config & paths (foundation — full code, TDD)

**Files**: Create `gladius.py` (module header + this stage's block), `test_gladius.py`.

**Interfaces provided** (later stages import/use exactly these):
`CONFIG_DIR: Path` · `CONFIG_PATH: Path` · `DATA_DIR: Path` · `THUMB_DIR: Path` ·
`SET_DIR: Path` · `THUMB_HEIGHT = 500` · `class Config` (fields below) ·
`Config.load() -> Config` · `Config.save(self) -> None` · `pictures_dir() -> Path`.

**Steps**:
- [ ] `gladius.py` opens with:
  ```python
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
  ```
  (PySide6 imports are added by the stages that need them — Qt classes at module top from
  Stage 2 on: `from PySide6.QtCore import ...` etc.)
- [ ] Known-folder resolution (why: Brian's machines redirect Pictures away from
  `%USERPROFILE%`; `SHGetKnownFolderPath` returns the truth):
  ```python
  def pictures_dir() -> Path:
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
  ```
- [ ] The config dataclass — defaults are the public defaults (SPEC §5):
  ```python
  @dataclass
  class Config:
      wallpaper_path: str = ""          # "" → resolved to <Pictures>\Wallpapers at load
      recursive: bool = True
      number_of_pictures: int = 7
      border_color: str = "#C27B63"
      backdrop: str = "dim"             # "dim" | "acrylic"
      dim_opacity: float = 0.7
      shear: bool = True
      fit_mode: str = "fill"            # key of FIT_MODES (Stage 3)
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
  ```
- [ ] Tests first (in `test_gladius.py`; note the env-patching pattern so tests never touch
  the real `%APPDATA%`):
  ```python
  import json
  import tempfile
  import unittest
  from pathlib import Path
  from unittest import mock

  import gladius


  class ConfigTests(unittest.TestCase):
      def setUp(self):
          self.tmp = tempfile.TemporaryDirectory()
          self.cfg_path = Path(self.tmp.name) / "config.json"
          self.p1 = mock.patch.object(gladius, "CONFIG_DIR", Path(self.tmp.name))
          self.p2 = mock.patch.object(gladius, "CONFIG_PATH", self.cfg_path)
          self.p1.start(); self.p2.start()
          self.addCleanup(self.p1.stop)
          self.addCleanup(self.p2.stop)
          self.addCleanup(self.tmp.cleanup)

      def test_first_run_creates_defaults(self):
          cfg = gladius.Config.load()
          self.assertTrue(self.cfg_path.exists())
          self.assertEqual(cfg.number_of_pictures, 7)
          self.assertTrue(cfg.wallpaper_path.endswith("Wallpapers"))

      def test_partial_file_merges_defaults(self):
          self.cfg_path.write_text(json.dumps({"number_of_pictures": 5, "junk_key": 1}))
          cfg = gladius.Config.load()
          self.assertEqual(cfg.number_of_pictures, 5)
          self.assertEqual(cfg.fit_mode, "fill")
          self.assertFalse(hasattr(cfg, "junk_key"))

      def test_corrupt_file_falls_back(self):
          self.cfg_path.write_text("{not json")
          cfg = gladius.Config.load()
          self.assertEqual(cfg.border_color, "#C27B63")

      def test_clamps(self):
          self.cfg_path.write_text(json.dumps({"number_of_pictures": 99,
                                               "dim_opacity": 7, "backdrop": "vanta"}))
          cfg = gladius.Config.load()
          self.assertEqual(cfg.number_of_pictures, 15)
          self.assertEqual(cfg.dim_opacity, 1.0)
          self.assertEqual(cfg.backdrop, "dim")
  ```

**Verification**: `python -m unittest test_gladius -v` → 4 tests pass.
Commit: `stage 1: config + known-folder paths`.

---

## Stage 2 — Scan & thumbnail cache (foundation — full code, TDD for the pure parts)

**Files**: Modify `gladius.py` (append), `test_gladius.py` (append).

**Interfaces provided**:
`WALLPAPER_EXTS: frozenset[str]` · `scan_wallpapers(cfg: Config) -> list[Path]` ·
`thumb_key(p: Path) -> str` · `class ThumbCache(QObject)` with signal
`thumb_ready = Signal(int)`, methods `start()`, `thumb_path(i: int) -> Path`, and
constructor `ThumbCache(files: list[Path], batch: int)`.

**Steps**:
- [ ] Add to module imports: `from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal`
      and `from PySide6.QtGui import QImage`.
- [ ] Scan (recursive by default — the wallpapers live in subfolders; sorted
      case-insensitively for a stable strip order):
  ```python
  WALLPAPER_EXTS = frozenset(
      {".jpg", ".jpeg", ".jfif", ".png", ".bmp", ".webp", ".gif", ".avif"})

  def scan_wallpapers(cfg: Config) -> list[Path]:
      root = Path(cfg.wallpaper_path)
      if not root.is_dir():
          return []
      it = root.rglob("*") if cfg.recursive else root.glob("*")
      files = [p for p in it if p.is_file() and p.suffix.lower() in WALLPAPER_EXTS]
      return sorted(files, key=lambda p: str(p).lower())
  ```
- [ ] Cache key — `sha1(abs_path | mtime_ns | size)`: any rename, move, or edit produces a
      new key, which kills hyprquickpaper's stale-thumb and basename-collision bugs:
  ```python
  def thumb_key(p: Path) -> str:
      st = p.stat()
      raw = f"{p.resolve()}|{st.st_mtime_ns}|{st.st_size}"
      return hashlib.sha1(raw.encode("utf-8", "surrogatepass")).hexdigest() + ".jpg"
  ```
- [ ] The cache. One worker per image; the pool width is `cache_batch_size` (parity with the
      original's meaning: parallel thumbnail jobs). Workers signal the tile index so the UI
      repaints exactly one tile — this replaces the original's retry-timer hack and fixes
      its blank-first-run race:
  ```python
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
          for stale in THUMB_DIR.iterdir():        # prune orphans (renamed/edited/deleted sources)
              if stale.name not in expected:
                  try:
                      stale.unlink()
                  except OSError:
                      pass
          for i, src in enumerate(self.files):
              dst = self.thumb_path(i)
              if not dst.exists():
                  self.pool.start(_ThumbWorker(i, src, dst, self._signals))
  ```
- [ ] Tests (pure parts — scan + key; the QThreadPool path is exercised live in Stage 6):
  ```python
  class ScanTests(unittest.TestCase):
      def test_recursive_scan_filters_and_sorts(self):
          with tempfile.TemporaryDirectory() as d:
              root = Path(d)
              (root / "sub").mkdir()
              (root / "b.jpg").write_bytes(b"x")
              (root / "sub" / "a.PNG").write_bytes(b"x")
              (root / "notes.txt").write_bytes(b"x")
              cfg = gladius.Config(wallpaper_path=d, recursive=True)
              names = [p.name for p in gladius.scan_wallpapers(cfg)]
              self.assertEqual(names, ["b.jpg", "a.PNG"])  # sorted by full lowered path
              cfg2 = gladius.Config(wallpaper_path=d, recursive=False)
              self.assertEqual([p.name for p in gladius.scan_wallpapers(cfg2)], ["b.jpg"])

      def test_missing_dir_returns_empty(self):
          cfg = gladius.Config(wallpaper_path=r"C:\definitely\not\here")
          self.assertEqual(gladius.scan_wallpapers(cfg), [])


  class ThumbKeyTests(unittest.TestCase):
      def test_key_changes_with_content(self):
          with tempfile.TemporaryDirectory() as d:
              f = Path(d) / "w.jpg"
              f.write_bytes(b"one")
              k1 = gladius.thumb_key(f)
              f.write_bytes(b"three!")      # different size ⇒ different key even if mtime ties
              k2 = gladius.thumb_key(f)
              self.assertNotEqual(k1, k2)
              self.assertTrue(k1.endswith(".jpg"))
  ```
  *(Sort expectation: ordering is by full lowered path, so `<tmp>\b.jpg` sorts before
  `<tmp>\sub\a.png` — the assertion `["b.jpg", "a.PNG"]` is correct as written.)*

**Verification**: `python -m unittest test_gladius -v` → all green (7 tests).
Commit: `stage 2: scan + thumbnail cache`.

---

## Stage 3 — Wallpaper setter (foundation — full code, TDD for the pure parts)

**Files**: Modify `gladius.py` (append), `test_gladius.py` (append).

**Interfaces provided**:
`FIT_MODES: dict[str, tuple[str, str]]` · `DIRECT_EXTS: frozenset[str]` ·
`set_wallpaper(path: Path, fit_mode: str) -> bool` ·
`build_select_command(template: str, path: Path) -> str` ·
`select_wallpaper(path: Path, cfg: Config) -> bool` ·
`get_current_wallpaper() -> str`.

**Steps**:
- [ ] Fit-mode → registry value pairs (`WallpaperStyle`, `TileWallpaper`):
  ```python
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
  ```
- [ ] The setter. Format guard: anything outside `DIRECT_EXTS` (webp/gif/avif), or a failed
      SPI call, goes through a PNG transcode in `%LOCALAPPDATA%\Gladius\set\` — Windows'
      `SystemParametersInfoW` chokes on webp (renders black or fails) even though QImage
      reads it fine:
  ```python
  def _apply_fit_mode(fit_mode: str) -> None:
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
  ```
- [ ] Tests (pure logic; no test writes the real registry or wallpaper):
  ```python
  class SetterLogicTests(unittest.TestCase):
      def test_fit_mode_pairs(self):
          self.assertEqual(gladius.FIT_MODES["fill"], ("10", "0"))
          self.assertEqual(gladius.FIT_MODES["tile"], ("0", "1"))
          self.assertEqual(len(gladius.FIT_MODES), 6)

      def test_build_select_command(self):
          cmd = gladius.build_select_command(
              'wal -i "{path}"', Path(r"C:\pics\a b.jpg"))
          self.assertEqual(cmd, f'wal -i "{Path(r"C:/pics/a b.jpg").resolve()}"')

      def test_direct_exts_exclude_webp(self):
          self.assertNotIn(".webp", gladius.DIRECT_EXTS)
          self.assertIn(".jfif", gladius.DIRECT_EXTS)

      def test_set_wallpaper_transcodes_non_direct(self):
          calls = []
          with mock.patch.object(gladius, "_apply_fit_mode"), \
               mock.patch.object(gladius, "_spi_set",
                                 side_effect=lambda p: calls.append(p) or True), \
               mock.patch.object(gladius, "_transcode_to_png",
                                 return_value=Path("C:/fake/current.png")) as tr:
              ok = gladius.set_wallpaper(Path("C:/pics/x.webp"), "fill")
          self.assertTrue(ok)
          tr.assert_called_once()
          self.assertEqual(calls, [Path("C:/fake/current.png")])
  ```

**Verification**: `python -m unittest test_gladius -v` → all green. **Plus one real smoke**
(this is safe and reversible — note the current wallpaper first via
`python -c "import gladius; print(gladius.get_current_wallpaper())"`):
`python -c "import gladius, pathlib; print(gladius.set_wallpaper(pathlib.Path(sorted((pathlib.Path(gladius.Config.load().wallpaper_path)).rglob('*.jpg'))[0]), 'fill'))"`
→ prints `True` and the desktop wallpaper visibly changes. Restore the noted original with
the same one-liner if desired. Commit: `stage 3: win32 wallpaper setter`.

---

## Stage 4 — CLI entry, single instance, `--random` (foundation — full code)

**Files**: Modify `gladius.py` (append), `test_gladius.py` (append).

**Interfaces provided**: `acquire_single_instance() -> bool` · `pick_random(files, avoid) ->
Path | None` · `main(argv: list[str] | None = None) -> int` · module runnable via
`if __name__ == "__main__": sys.exit(main())`.
The overlay entry `run_overlay(cfg) -> int` is a **forward declaration**: Stage 4 defines a
stub that prints `"overlay not built yet (stage 6)"` and returns `2`; Stage 6 replaces the
stub's body. This is deliberate so `--random` ships and is testable before any GUI exists.

**Steps**:
- [ ] Single instance (named mutex; handle intentionally leaked — the OS frees it at exit):
  ```python
  def acquire_single_instance() -> bool:
      kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
      kernel32.CreateMutexW(None, False, "GladiusWallpaperPicker")
      return ctypes.get_last_error() != 183     # ERROR_ALREADY_EXISTS
  ```
- [ ] Random pick avoids repeating the current wallpaper when there's a choice:
  ```python
  def pick_random(files: list[Path], avoid: str) -> Path | None:
      if not files:
          return None
      pool = [p for p in files if str(p.resolve()) != avoid] or files
      return random.choice(pool)
  ```
- [ ] Entry point:
  ```python
  def run_overlay(cfg: Config) -> int:          # replaced wholesale in Stage 6
      print("overlay not built yet (stage 6)")
      return 2

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
  ```
- [ ] Tests:
  ```python
  class RandomPickTests(unittest.TestCase):
      def test_avoids_current_when_possible(self):
          a, b = Path(r"C:\w\a.jpg"), Path(r"C:\w\b.jpg")
          for _ in range(20):
              self.assertEqual(gladius.pick_random([a, b], str(a.resolve())), b)

      def test_single_file_still_returned(self):
          a = Path(r"C:\w\a.jpg")
          self.assertEqual(gladius.pick_random([a], str(a.resolve())), a)

      def test_empty_returns_none(self):
          self.assertIsNone(gladius.pick_random([], ""))
  ```

**Verification**: tests green; then live: `python gladius.py --config` prints the
`%APPDATA%` path; `python gladius.py --random` visibly changes the wallpaper and exits 0
(`$LASTEXITCODE` → 0); `python gladius.py` prints the stage-6 stub line. (The double-launch
mutex check is meaningful only once the overlay stays open — it's exercised in Stage 8's
checklist, not here.) Commit: `stage 4: cli, single-instance, --random`.

---

## Stage 5 — StripView (the heart — full code)

**Files**: Modify `gladius.py` (append). No unit tests — this is paint/input code; its
verification is visual via the `--windowed` debug run wired in Stage 6. (To eyeball it
before Stage 6 exists, the executor may temporarily point `run_overlay` at a bare window
hosting a StripView — throwaway, not committed.)

**Interfaces provided**: `class StripView(QWidget)`:
- `StripView(files: list[Path], cache: ThumbCache, cfg: Config, parent=None)`
- `index: int` (current selection) · signal `index_changed = Signal(int)` ·
  signal `picked = Signal(int)` (mouse click = select-and-set, parity with the original)
- `move(delta: int)` (±1) · `page(delta: int)` (±number_of_pictures) ·
  `set_index(i: int)` · `relayout()` (call after `number_of_pictures` changes)
- slot `on_thumb_ready(i: int)`

**Layout math — ported from the original (`shell.qml`), constants preserved**:
tile width `w/n − 10`, spacing `4`, step `tile_w + 4`; ensure-visible uses the original's
`itemEnd = itemStart + tileWidth + 20` slack; scroll clamps to `[0, content_w − width]`.
Key-scroll animates 100 ms; page jumps use the same duration (the original varied velocity,
not duration — with a fixed-duration animation the page jump is simply a longer glide, same
feel).

**Steps**:
- [ ] Add imports: `from PySide6.QtCore import Qt, QVariantAnimation, QEasingCurve, QRectF, QPointF`
      · `from PySide6.QtGui import QPainter, QPixmap, QColor, QPen` ·
      `from PySide6.QtWidgets import QWidget`.
- [ ] The class, verbatim:
  ```python
  SPACING = 4
  SHEAR_X = -0.25          # the original's parallelogram lean
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

      # --- geometry (original's math) ---
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

      # --- selection API (overlay calls these) ---
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
          self._pixmaps.pop(i, None)           # drop any placeholder-miss cache
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
  ```

**Verification**: `python -m unittest test_gladius -v` still green (no regressions —
StripView imports cleanly: `python -c "import gladius"` exits 0). Visual check lands with
Stage 6. Commit: `stage 5: strip view`.

---

## Stage 6 — Overlay window (full code; consumes Stage R findings)

**Files**: Modify `gladius.py` (append new code; **replace** the Stage-4
`run_overlay` stub body). `RESEARCH-notes.md` consulted for R1/R2 verdicts.

**Interfaces provided**: `class Overlay(QWidget)` · real `run_overlay(cfg) -> int` ·
`enable_acrylic(hwnd: int) -> bool` (body per R1; returns False on any failure).
`Overlay` exposes `apply_setting(key: str) -> None` for Stage 7.

**Steps**:
- [ ] Add imports: `from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout` ·
      `from PySide6.QtGui import QCursor, QGuiApplication, QKeyEvent`.
- [ ] `enable_acrylic(hwnd)` — paste the winning R1 attempt verbatim inside a
      `try/except Exception: return False`; if R1 concluded "none works", the body is just
      `return False`.
- [ ] The overlay:
  ```python
  class Overlay(QWidget):
      def __init__(self, cfg: Config, files: list[Path], cache: ThumbCache):
          flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
          super().__init__(None, flags)
          self.cfg, self.files, self.cache = cfg, files, cache
          self.setAttribute(Qt.WA_TranslucentBackground)   # drop if R1 said acrylic needs opaque
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

          # start on the currently-set wallpaper when it's in the list (QoL, SPEC §3)
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
          if getattr(self.cfg, "_windowed", False):        # debug: normal 1600×500 window
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
              p.fillRect(self.rect(), QColor(0, 0, 0, 60))   # light tint over blur
          else:
              p.fillRect(self.rect(),
                         QColor(0, 0, 0, int(self.cfg.dim_opacity * 255)))
          p.end()

      # --- keys (SPEC §3 table) ---
      def keyPressEvent(self, ev: QKeyEvent) -> None:
          if self.settings is not None and self.settings.isVisible():
              self.settings.handle_key(ev)                 # Stage 7; Esc/S close it there
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
  ```
- [ ] Replace the Stage-4 stub:
  ```python
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
  ```

**Verification** (visual, live):
1. `python gladius.py --windowed` → a strip window appears; first cold run shows
   "Loading…" tiles that fill in live; J/K/D/U/arrows move the border; footer tracks
   `name  i / 72`; wheel + drag scroll; Esc exits without changing the wallpaper.
2. `python gladius.py` (fullscreen, komorebi running) → overlay covers the screen above all
   tiles, keys work, Space sets the wallpaper and exits. Watch komorebi: no retiling (R2's
   verdict predicted this; Stage 8 formalizes the check).
3. Second cold-vs-warm run: warm start feels instant (thumbs cached).
Commit: `stage 6: overlay window`.

---

## Stage 7 — Settings pane (full code)

**Files**: Modify `gladius.py` (append; wire `self.settings = SettingsPane(self)` into
`Overlay.__init__` replacing the `None`).

**Interfaces provided**: `class SettingsPane(QWidget)` — constructor `SettingsPane(overlay:
Overlay)`; methods `toggle()`, `handle_key(ev: QKeyEvent)`. Reads/writes
`overlay.cfg`, calls `overlay.apply_setting(key)` after every change (which saves).

**Rows model** (order fixed; each row: config key, display label, value cycle):
```python
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
```
Free-form hex border colors stay a config-file edit (SPEC §3); if the current config value
isn't in a row's cycle, cycling starts from the nearest/first entry without destroying the
custom value until the user actually cycles that row.

**Steps**:
- [ ] The pane — a centered card, custom-painted rows, keyboard-only:
  ```python
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
              i = 0 if delta > 0 else len(values) - 1   # custom value → enter cycle at edge
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
  ```
- [ ] In `Overlay.__init__`, replace `self.settings = None` with
      `self.settings = SettingsPane(self)`.

**Verification** (live, `--windowed` then fullscreen): `S` opens the card; J/K move the
highlight; H/L cycle values — shear toggles visibly, border color swatches change the strip
border immediately, visible-tiles re-lays the strip, backdrop dim↔acrylic switches (or
silently stays dim per R1); every change survives restart
(`python gladius.py --config` → open the JSON, confirm the new values); Esc closes the pane,
second Esc exits the app. Commit: `stage 7: settings pane`.

---

## Stage 8 — System integration + live acceptance (the gate)

**Files**: Modify `~/.config/whkdrc` (append one line) — outside the repo, Brian's dotfiles.
Possibly modify `~/applications.json` (only if R2 failed). `DECISIONS.md` gets the komorebi
outcome entry. No code changes expected.

**Steps**:
- [ ] Resolve the pythonw path recorded in Stage 0 (e.g. `(Get-Command pythonw).Source`).
      Append to `~/.config/whkdrc` under the "Launch terminal" section
      (verified free on 2026-08-20 — only `alt+shift+w` is taken):
      ```
      # --- Gladius wallpaper picker (Alt+W) ---
      alt + w                 : & '<pythonw path>' 'C:\path\to\Gladius\gladius.py'
      ```
- [ ] Restart whkd (it reads config at startup ONLY): find the running binary's path
      (`(Get-Process whkd).Path`), then `Stop-Process -Name whkd -Force;
      Start-Process '<that path>' -WindowStyle Hidden`. Confirm other bindings still work
      (e.g. Alt+J moves focus) before proceeding.
- [ ] **Only if R2 failed**: add the float rule to `~/applications.json` per komorebi's
      schema (an entry matching the window by exe `pythonw.exe` + title "gladius" — set
      `overlay.setWindowTitle("gladius")` in `Overlay.__init__` first if not already
      matching), then `komorebic reload-configuration`. Re-test.
- [ ] **Live acceptance checklist** (SPEC §9 verbatim — every box, on the real machine,
      komorebi running):
      - [ ] `Alt+W` summons the overlay in ≲1.5 s warm; floats above everything; komorebi
            does not tile/resize/retile-fight it.
      - [ ] First cold run: placeholders appear immediately, thumbs stream in; second run:
            instant.
      - [ ] All keys per SPEC §3 (J/K/D/U/arrows/Space/Enter/Esc/S); wheel, drag, click.
      - [ ] Selecting a `.jpg`, a `.png`, and the `.jfif` each sets the wallpaper with fit
            mode respected. Plant a `.webp` test file in the wallpaper folder (copy any
            image, convert via
            `python -c "from PySide6.QtGui import QImage,QGuiApplication;app=QGuiApplication([]);QImage(r'<src.jpg>').save(r'<wallpapers>\test.webp','WEBP')"`),
            select it → transcode path works (wallpaper visibly correct, and
            `%LOCALAPPDATA%\Gladius\set\current.png` exists). Delete the test file after;
            note: creating it in the wallpaper folder is the *user's* action for a test —
            Gladius itself still never writes there.
      - [ ] `python gladius.py --random` changes the wallpaper with no window.
      - [ ] Settings pane rows all apply live and survive restart.
      - [ ] Double-launch (hotkey twice fast) → one overlay only.
      - [ ] Esc leaves the desktop untouched.
- [ ] Append the DECISIONS.md entry: date, komorebi strategy verdict (Tool-only or
      +rule), acrylic verdict (A/B/none), any deviation from this blueprint. Add it to the
      DECISIONS index.

**Verification**: the checklist above IS the verification. All boxes ticked → commit:
`stage 8: system integration + live acceptance`.

---

## Stage 9 — Public-readiness docs

**Files**: Create `LICENSE`. Modify `README.md` (complete it), `CLAUDE.md` (status line),
`ROADMAP.md` (Current focus + phase ticks).

**Steps**:
- [ ] `LICENSE`: MIT, `Copyright (c) 2026 Brian Gomez`, standard text verbatim.
- [ ] Complete `README.md` for a stranger: what it is (+ the demo-worthy pitch), install
      (`pip install PySide6`, clone, run), full keybind table (SPEC §3), config reference
      table (every key of `Config` with default + meaning), integration guide (whkd line
      with a placeholder path + "whkd reads config at startup only — restart it"; komorebi
      note per the R2 outcome; Task-Scheduler `--random` recipe), credits (hyprquickpaper
      link, "original reimplementation, no code shared"), MIT badge/mention. Keep the
      six-doc table. Remove the "under construction" banner.
- [ ] `CLAUDE.md`: update **Pitch & status** → "v1 shipped <date>; maintenance mode."
- [ ] `ROADMAP.md`: tick phases 2–3, set Current focus to post-v1 state (next: pre-release
      gate → public), keep the gate checklist unticked for Brian's pass.
- [ ] Grep-audit for the public gate (informational now, gating later):
      `git grep -iE "brian|UserData|Projects"` — hits allowed only in
      `LICENSE` (copyright) and ROADMAP/DECISIONS/ARCHIVE (private-history docs Brian may
      choose to squash before flipping public; flag them in the session report).
- [ ] Commit: `stage 9: license + public-facing docs`.

**Verification**: fresh-eyes read of README top-to-bottom — a stranger could install and
run from it alone; `python -m unittest test_gladius -v` full suite green one last time.

---

## Coverage map (SPEC § → stage)

| SPEC section | Stage |
|---|---|
| §1 identity, single file, MIT | 0, 1–7, 9 |
| §2 parity table + 3 bug fixes | 2 (cache/scan), 5 (strip/keys/mouse), 6 (keys), 3 (select command) |
| §3 UX: strip, footer, keys, settings | 5, 6, 7 |
| §4 setter, format guard, `--random`, fit modes | 3, 4 |
| §5 config & data dirs | 1, 2 |
| §6 architecture | 1–7 (one file, section order as listed) |
| §7 whkd + komorebi | R2, 8 |
| §8 repo & docs | 0, 9 |
| §9 acceptance | 8 |
| §10 unknowns | R |
