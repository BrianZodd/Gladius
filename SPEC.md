# ⏳ TEMPORARY — DELETE WHEN: v1 is built, tested live, and this spec's essence is distilled into CLAUDE.md / ROADMAP.md / ARCHIVE.md

# Gladius — Design Spec (approved via nova-forge, 2026-08-20)

## 1. Identity

**Gladius** is a keyboard-driven wallpaper picker overlay for Windows — a faithful port of
[hyprquickpaper](https://github.com/iamsurjog/hyprquickpaper) (QML/Quickshell/Wayland) to
Python 3.12 + PySide6 (LGPL). A standalone launcher, not a daemon: a hotkey summons a
fullscreen translucent overlay showing a horizontal strip of wallpaper thumbnails; the user
scrolls with vim keys, picks one, the desktop wallpaper changes, the app exits.

- **Deliverable**: one well-structured Python file (`gladius.py`) + auto-created JSON config.
- **License / audience**: MIT, free and open source. Repo private now, public later — so no
  machine-specific paths are committed anywhere; everything Brian-specific lives in his local
  `%APPDATA%\Gladius\config.json` (never committed) or in his dotfiles repos (whkdrc).
- **Lifecycle**: short build, then maintenance-only (bug fixes).
- **Reference code**: hyprquickpaper has **no license file** → lessons only, zero code reuse.
  Full rewrite anyway (QML→Qt Widgets, swww→Win32).

## 2. Parity with the original (sweep findings)

Every behavior the original has, Gladius has. From reading `shell.qml`, `cache.sh`,
`commands.sh`, `config.json`, `README.md`:

| Original | Gladius |
|---|---|
| Horizontal strip of sheared (parallelogram, xFactor −0.25) tiles, ~500px tall | Same look: horizontal strip, shear optional (default **on**), tile height scales to screen (~50% of screen height) |
| `number_of_pictures` visible tiles (default 7) | Same config key, same meaning |
| J/K = ±1 tile, D/U = ±1 screenful | Same, plus ←/→ arrows as J/K synonyms |
| Space/Enter select, Esc quit | Same |
| Mouse wheel scrolls; click-drag scrolls; click selects | Same |
| Selected tile gets colored border (`border_color`) | Same config key |
| Smooth animated scroll (~100ms), faster on page jumps | Same (QVariantAnimation, OutCubic) |
| Async thumbnail cache built at launch; tiles show "Loading…" placeholder and retry until their thumb appears | Same via QThreadPool workers + per-thumb Qt signal → repaint (no polling/retry-timer hack) |
| `cache_batch_size` limits parallel thumbnail jobs | Same key = worker thread count |
| Selection runs a user-defined command with the image path (`commands.sh`) | `on_select_command` config key with `{path}` placeholder; **default null → built-in Win32 setter** (§4) |
| Config hot-reload (FileView watchChanges) | Settings panel (§3) covers live changes; hot-reload of the file itself is out — the app lives for seconds at a time |

**Original bugs Gladius explicitly fixes** (their README's "common fixes" section documents both):
1. *Stale cache* — original keys thumbs by filename only; renaming/replacing an image shows the
   old thumb until you wipe the cache. → Gladius keys by `sha1(abs_path | mtime | size)`.
2. *Blank first run* — original races its cache script; first launch shows nothing until
   restart. → thumbs generate in-process and signal the UI per-thumb; placeholders fill in live.
3. *Name collisions* — original's cache flattens `find` (recursive) results by basename.
   → hash keys make collisions impossible; scanning is recursive by design (Brian's 72
   wallpapers live in subfolders).

## 3. UX

**Launch → overlay** on the monitor containing the cursor: frameless, always-on-top,
fullscreen, translucent. Backdrop per setting: **dim** (default; ~70% black over the desktop)
or **acrylic** (Win11 blur-behind; if the API fails, falls back to dim silently).

**Strip**: vertically centered. Tiles cropped to fill (PreserveAspectCrop equivalent),
sheared when `shear: true`. Selection border 4px in `border_color` (default `#C27B63`, the
original's). Selection starts on the **currently-set wallpaper if it's in the list**, else
tile 0 (small QoL divergence: the original always starts at 0).

**Footer**: centered under the strip — highlighted file's name + `12 / 72` position counter.

**Keys**:
| Key | Action |
|---|---|
| `J` / `→` | next tile |
| `K` / `←` | previous tile |
| `D` | forward one screenful (`number_of_pictures`) |
| `U` | back one screenful |
| `Space` / `Enter` | set wallpaper, exit |
| `Esc` | exit, no change (closes settings pane first if open) |
| `S` | toggle settings pane |
Mouse: wheel scrolls the strip, click-drag scrolls, click on a tile selects-and-sets.

**Settings pane** (`S`): a slide-in panel over the strip, keyboard-navigable
(J/K or ↑/↓ move between rows; H/L or ←/→ cycle the row's value; Esc/S close). Rows:
backdrop style (dim/acrylic) · dim opacity · shear on/off · border color (cycle a curated
palette; free-form hex stays a config-file edit) · fit mode (fill/fit/span/stretch/center/tile)
· visible tiles (3–15). Every change **applies live** to the open overlay and **saves to
config.json immediately**. No live preview of wallpapers themselves (v1 decision — noted in
ROADMAP as a possible v2 with debounce+restore).

## 4. Setting the wallpaper (Win32)

1. Write fit mode: `HKCU\Control Panel\Desktop` → `WallpaperStyle` + `TileWallpaper`
   (fill=10, fit=6, span=22, stretch=2, center=0, tile=0/1). Only when the value differs.
2. `ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, abs_path, 0x3)`
   (SPI_SETDESKWALLPAPER, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE). No elevation needed.
3. **Format guard**: `.jpg/.jpeg/.jfif/.png/.bmp` pass straight through (verified: Brian's 72
   files are exactly these). Any other extension (webp/avif/gif/…) — or an SPI call that
   returns 0 — → load via QImage, save PNG to `%LOCALAPPDATA%\Gladius\set\current.png`, set
   that path instead. QImage reads webp out of the box in PySide6.
4. If `on_select_command` is set, it **replaces** steps 1–3: run it detached with `{path}`
   substituted (parity with the original's `commands.sh` contract).

`--random`: scan → pick random → steps 1–4 → exit. No UI, no thumbnails touched. Usable from
a logon scheduled task for wallpaper-on-boot rotation.

Non-goals v1 (ROADMAP items, not build items): per-monitor wallpapers via `IDesktopWallpaper`
COM; swww-style animated transitions (impossible via SPI; would need a full-screen fade
window — pure v2 polish); grid layout mode; live preview while scrolling; tray/daemon mode.

## 5. Data & config

- **Config**: `%APPDATA%\Gladius\config.json`. Auto-created with defaults on first run —
  a public-repo-friendly design: nothing user-specific ships in the repo. Keys:
  ```json
  {
    "wallpaper_path": "<Known-Folder Pictures>\\Wallpapers",
    "recursive": true,
    "number_of_pictures": 7,
    "border_color": "#C27B63",
    "backdrop": "dim",
    "dim_opacity": 0.7,
    "shear": true,
    "fit_mode": "fill",
    "cache_batch_size": 8,
    "on_select_command": null
  }
  ```
  `wallpaper_path` default resolves the *actual* Pictures known folder via
  `SHGetKnownFolderPath` — critical on Brian's machines where user folders are redirected to
  `D:\UserData\` / `E:\UserData\`; `%USERPROFILE%\Pictures` would silently miss them.
- **Thumb cache**: `%LOCALAPPDATA%\Gladius\thumbs\<sha1>.jpg` (quality 85, height 500,
  aspect-preserved). Orphans (source gone/changed) pruned in a background thread at launch.
- **Transcode scratch**: `%LOCALAPPDATA%\Gladius\set\current.png`, overwritten per use.

## 6. Architecture

Single file `gladius.py` (~700 lines), stdlib + PySide6 only. Sections top-to-bottom:

- `Config` — load/merge-defaults/save; dataclass-backed.
- `scan_wallpapers(path, recursive) -> list[Path]` — sorted, extension-filtered
  (`.jpg .jpeg .jfif .png .bmp .webp .gif .avif` — anything QImage can read; the setter's
  format guard handles what Windows can't).
- `ThumbCache(QObject)` — QThreadPool (`cache_batch_size` threads) of QRunnable workers;
  `thumb_ready(index)` signal; prune pass.
- `set_wallpaper(path, fit_mode)` + `run_select_command(...)` — §4 logic, importable-clean so
  `--random` uses it without any QWidget.
- `StripView(QWidget)` — **custom-painted** strip (one widget, one paintEvent): full control
  over shear (QTransform), crop, border, animated `content_x` (QVariantAnimation), and the
  ensure-visible math ported from the original. Chosen over QListView: the shear transform and
  animated selection don't fit the delegate model without fighting it.
- `SettingsPane(QWidget)` — the §3 panel; emits `changed(key, value)`; overlay applies + saves.
- `OverlayWindow(QWidget)` — frameless fullscreen top-level; wires keys, footer, backdrop,
  pane; `Qt.Tool` flag (→ WS_EX_TOOLWINDOW) so **komorebi never manages it** (primary
  strategy; fallback below). Acrylic via DWM backdrop attribute, dim fallback on failure.
- `main()` — argparse (`--random`, `--config` to print config path), single-instance guard
  (`CreateMutexW` named mutex; second launch exits 0 silently), QApplication, run.

## 7. System integration (Brian's machine — documented in README for others)

- **Hotkey**: `~/.config/whkdrc` — `alt + w` is **verified free** (checked 2026-08-20; only
  `alt+shift+w` = retile is taken). Line:
  `alt + w : & 'C:\path\to\pythonw.exe' 'C:\path\to\Gladius\gladius.py'`
  (executor verifies the real pythonw path; `pythonw` = no console flash). **whkd reads config
  at startup only** → restart whkd after editing.
- **komorebi**: primary = `Qt.Tool` window style, komorebi should never see it. Live-test
  under running komorebi; if it still tiles or steals focus, add the float rule to
  `~/applications.json` as fallback. Test result gets logged in DECISIONS.md.
- **Dependencies**: `pip install PySide6` (only dep). `requirements.txt` pins it.

## 8. Repo & docs

- Nova six-doc system from day one (CLAUDE / ROADMAP / ARCHIVE / DECISIONS / AGENTS / README),
  set up via nova-documentation in the planning session. README written for the eventual
  public audience: hero description, install, usage/keys table, config reference, whkd +
  komorebi integration guide, credits to hyprquickpaper, MIT badge.
- `LICENSE` = MIT. `.gitignore`: `__pycache__/`, local scratch. Git repo initialized private.
- Every-session ritual: dated DECISIONS.md entry.

## 9. Acceptance criteria (live-tested before "done")

1. `alt+w` (via whkd) summons the overlay in ≲1.5s warm; overlay floats above everything and
   komorebi does not tile, resize, or retile-fight it.
2. First cold run: placeholders appear immediately, thumbs stream in; second run: instant.
3. All keys per §3 table; wheel, drag, click all work.
4. Selecting a `.jpg`, a `.png`, and a `.jfif` each changes the wallpaper correctly with
   fit-mode respected; a planted `.webp` test file goes through the transcode path and works.
5. `gladius.py --random` changes the wallpaper with no window.
6. Settings pane: every row applies live and survives restart (config.json updated).
7. Double-launch does not spawn two overlays.
8. Esc leaves the desktop untouched.

## 10. Known unknowns → blueprint Stage R

- Acrylic on a frameless Qt window (DWM `DWMWA_SYSTEMBACKDROP_TYPE` vs the undocumented
  `SetWindowCompositionAttribute`) — spike with graceful dim fallback; must not block v1.
- Whether `Qt.Tool` alone truly hides Gladius from komorebi's window manager on this machine —
  live test decides primary vs applications.json fallback.
