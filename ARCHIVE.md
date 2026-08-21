# Gladius — ARCHIVE

Medium-essence detail retired from CLAUDE.md — retired specs, exhaustive reference, deep design notes. Fills as the project grows; nothing is ever lost (git history is the floor).

> **Section-scoped.** Read freely — no permission ask — but only the section you need (grep the header → offset-read). Don't load the whole file for a small answer.

## Index
- 2026-08-20 — v1 design reference (distilled from SPEC.md before it self-destructed)
- 2026-08-20 — v1 build record (distilled from BLUEPRINT.md + RESEARCH-notes.md)

---

## 2026-08-20 — v1 design reference (distilled from SPEC.md before it self-destructed)

`SPEC.md` was the approved design from the nova-forge session. v1 shipped to it; the parts
worth keeping are below. The *reasoning* behind these calls lives in DECISIONS.md
(2026-08-20 — Founding design calls); the user-facing description lives in README.md.

### Parity with hyprquickpaper

Every behaviour of the original is present. The mapping, as built:

| Original | Gladius |
|---|---|
| Horizontal strip of sheared tiles (parallelogram, xFactor −0.25), ~500px tall | Same, shear toggleable (default on); tile height scales with the strip, which is ~5/9 of screen height |
| `number_of_pictures` visible tiles (default 7) | Same key, same meaning, also the page-jump size |
| J/K = ±1 tile, D/U = ±1 screenful | Same, plus ←/→ as J/K synonyms |
| Space/Enter select, Esc quit | Same |
| Mouse wheel scrolls; click-drag scrolls; click selects | Same |
| Selected tile gets a `border_color` border | Same key, 4px |
| Smooth animated scroll (~100ms), faster on page jumps | Same duration via QVariantAnimation + OutCubic; a page jump is a longer glide |
| Async thumbnail cache; tiles show a placeholder and retry until their thumb appears | Same intent, better mechanism: QThreadPool workers emit a per-tile signal → that one tile repaints. No polling, no retry timer |
| `cache_batch_size` limits parallel thumbnail jobs | Same key = worker thread count |
| Selection runs a user command with the image path (`commands.sh`) | `on_select_command` with `{path}`; default null → the built-in Win32 setter |
| Config hot-reload (FileView watchChanges) | **Dropped deliberately** — the settings pane covers live changes and the app lives for seconds at a time |

Three upstream bugs are fixed rather than reproduced (stale thumbnails, blank first run,
basename collisions across subfolders) — see README "What's different from hyprquickpaper".

### Layout maths ported from the original

Tile width `w/n − 10`, spacing `4`, step `tile_w + 4`. Ensure-visible uses the original's
`itemEnd = itemStart + tileWidth + 20` slack; scroll clamps to `[0, content_w − width]`.
Shear factor `−0.25`. These constants are the reason the strip *feels* like the original —
they are not arbitrary and should not be "cleaned up" without a look at the result.

### Setting the wallpaper

1. Write fit mode to `HKCU\Control Panel\Desktop` → `WallpaperStyle` + `TileWallpaper`
   (fill 10, fit 6, span 22, stretch 2, center 0, tile 0/1).
2. `SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)`.
   No elevation needed.
3. Format guard: `.jpg/.jpeg/.jfif/.png/.bmp` pass straight through; anything else — or a
   direct attempt that fails — is loaded with QImage, written as PNG to
   `%LOCALAPPDATA%\Gladius\set\current.png`, and that path is set instead.
4. `on_select_command`, when set, replaces steps 1–3 entirely (fire-and-forget, detached).

### Non-goals recorded at design time

Not built for v1, by decision rather than omission: per-monitor wallpapers via
`IDesktopWallpaper` COM · animated set-transitions · grid layout · live preview while
scrolling · tray/daemon mode · config-file hot-reload · packaging (PyInstaller/PyPI).
Live candidates are tracked in ROADMAP → Active to-dos.

---

## 2026-08-20 — v1 build record (distilled from BLUEPRINT.md + RESEARCH-notes.md)

`BLUEPRINT.md` staged the build; `RESEARCH-notes.md` held the runtime spikes. Both
self-destructed on completion per their own headers. Verdicts and rationale are in
DECISIONS.md (2026-08-20 — v1 build session); the measurement detail worth keeping is here.

### How the build was staged

Bottom-up, one commit per stage: config → scan/cache → Win32 setter → CLI/`--random` →
StripView → Overlay → settings pane → integration/acceptance → public docs. Pure logic was
TDD'd with stdlib `unittest`; GUI stages were verified by driving the real widgets with
synthetic Qt events and by measuring captured frames. Two runtime unknowns were spiked
first (Stage R) because both could have forced design changes.

### R1 — acrylic blur measurement method

The useful part is the *method*, because the losing API reports success. Blur was judged by
high-frequency image energy — the standard deviation of a Laplacian convolution, normalised
by image standard deviation — captured two independent ways (Qt's `grabWindow`, and
`ffmpeg -f lavfi ddagrab`, i.e. DXGI desktop duplication). A real blur destroys
high-frequency detail while roughly preserving mean brightness; a flat panel destroys both.

Fullscreen, over a live desktop:

| variant | mean | stddev | HF ratio | reading |
|---|---|---|---|---|
| no window (baseline) | 0.558 | 0.063 | 4.15 | sharp desktop |
| translucent only, no API | 0.548 | 0.052 | 3.89 | detail passes straight through |
| `SetWindowCompositionAttribute` acrylic | 0.508 | 0.022 | **2.09** | genuine blur |
| `DWMWA_SYSTEMBACKDROP_TYPE` | 0.914 | 0.012 | 0.55 | flat opaque panel |

Two traps found, both worth remembering if this is ever revisited:

- Acrylic does **not** sample other top-most tool windows behind it — they composite as
  black. An early spike used such a window as its test backdrop and wrongly read as "no
  blur". It samples the desktop and ordinary windows normally, which is all Gladius sits over.
- ImageMagick statistics over a captured frame **with its alpha channel intact** are
  meaningless for this (a fully-dimmed region read as 0.5 grey). Flatten alpha before
  measuring; a dim backdrop then measures exactly linear — opacity 0.7 leaves 30% of the
  desktop's luminance, 1.0 leaves 0.

### R2 — how komorebi non-interference was measured

`komorebic state` is not queryable from a non-elevated shell on this machine (os error
10022), so komorebi was measured by its observable effect instead — which is the thing that
actually matters. Every visible top-level window (hwnd, exe, rect, ex-styles) was
snapshotted before, during, and after a fullscreen `Qt.Tool` window was held open, then
diffed: zero windows moved, the spike kept its exact requested geometry, and focus was taken
and returned. Confirmed afterwards with the real app under the real hotkey.

### Acceptance evidence worth keeping

Warm launch measured at **0.30 s** from process start to window visible (budget was 1.5 s).
A cold cache generated 72 thumbnails with placeholders painting first. Format matrix
verified against Windows' own `TranscodedImageCache` registry value, which records the exact
path Windows last transcoded a wallpaper from — a reliable oracle for "did the desktop
really take it", far better than trusting the API's return value.
