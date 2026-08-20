# ⏳ TEMPORARY — DELETE WHEN: BLUEPRINT.md dies (findings distilled into DECISIONS.md)

# Gladius — Stage R spike findings

Test rig: Windows 11 build 26200 · Python 3.12.10 · PySide6 6.11.2 · single 1920×1200
logical display at devicePixelRatio 1.5 (2880×1800 physical) · komorebi + whkd running
(komorebi elevated). Spike scripts were throwaway and live outside the repo.

---

## R1 — Acrylic blur on a frameless translucent Qt window

**Verdict (2026-08-20): Attempt B wins — `SetWindowCompositionAttribute` with
`ACCENT_ENABLE_ACRYLICBLURBEHIND`. `WA_TranslucentBackground` is KEPT (it did not have to
be dropped). Attempt A is rejected.**

Method: a frameless translucent always-on-top `Qt.Tool` window over known content, captured
two independent ways — Qt's own `QScreen.grabWindow(0)` (GDI) and `ffmpeg -f lavfi ddagrab`
(DXGI desktop duplication, which reflects true DWM composition). Blur was judged numerically
by high-frequency energy (stddev of a Laplacian convolution, normalised by image stddev):
a real blur destroys high-frequency detail while roughly preserving mean brightness.

Fullscreen measurements over a live desktop (the production geometry):

| variant | mean | stddev | HF ratio | reading |
|---|---|---|---|---|
| no window (baseline) | 0.558 | 0.063 | 4.15 | sharp desktop |
| translucent only, no API | 0.548 | 0.052 | 3.89 | detail passes straight through |
| **WCA acrylic** (attempt B) | 0.508 | 0.022 | **2.09** | **HF halved → genuine blur** |
| DWM systembackdrop (attempt A) | 0.914 | 0.012 | 0.55 | flat opaque panel |

- **Attempt A — `DwmSetWindowAttribute(DWMWA_SYSTEMBACKDROP_TYPE=38,
  DWMSBT_TRANSIENTWINDOW=3)`**: returns `S_OK` (hr=0) and is therefore *not* detectable by
  return code, but on a layered frameless window it paints a flat opaque light-grey panel —
  it obliterates the desktop instead of blurring it. Strictly worse than the dim fallback.
  Rejected. (Consequence: `enable_acrylic` cannot trust an API success code; the choice of
  attempt B is based on what it actually renders.)
- **Attempt B — `SetWindowCompositionAttribute` / `ACCENT_POLICY` with
  `AccentState = 4 (ACCENT_ENABLE_ACRYLICBLURBEHIND)`, `Attribute = 19 (WCA_ACCENT_POLICY)`**:
  returns 1 and renders a true blur-behind of the desktop *and* of ordinary windows, with
  Qt's translucency still enabled. Adopted.

**Deviation from the blueprint's literal constant**: the blueprint suggested
`GradientColor = 0x99000000`. That alpha (0x99 ≈ 60 %) plus the overlay's own tint renders
almost solid black — the blur is there but invisible under it. Measured a range and adopted
**`0x30000000`** (alpha 0x30) as the acrylic tint, which leaves the blur clearly visible;
the overlay's own paint tint over acrylic stays light (alpha 60, per blueprint).

**Caveat worth knowing** (does not affect Gladius): the acrylic backdrop does not sample
*other* top-most tool windows sitting behind it — those composite as black. It samples the
desktop and ordinary windows normally, which is all Gladius ever sits over. This is why an
early version of this spike, which used a top-most striped helper window as its test
backdrop, wrongly read as "no blur".

**Note on screenshots**: plain GDI screen capture and DXGI desktop duplication agreed in
every case here, so a GDI grab is trustworthy for judging this effect.

---

## R2 — Does `Qt.Tool` keep komorebi's hands off?

**Verdict (2026-08-20): PASS — `Qt.Tool` alone is sufficient. Stage 8 does NOT need the
`applications.json` float rule, and does not need a manual `WS_EX_TOOLWINDOW` style set.**

Method: a fullscreen frameless translucent `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
| Qt.Tool` window held open for 9 s under normally-running komorebi, with the full list of
visible top-level windows (hwnd, exe, rect, ex-styles) snapshotted before / during / after
and diffed. (`komorebic state` is not queryable from a non-elevated shell here — it fails
with os error 10022 — so komorebi's behaviour was measured by its observable effect on
window geometry instead, which is the thing that actually matters.)

Findings:

- The window is created with **`WS_EX_TOOLWINDOW` + `WS_EX_TOPMOST`** — confirmed by reading
  its ex-style back. `WS_EX_TOOLWINDOW` is precisely what komorebi's window filter skips.
- **komorebi never resized or moved it**: requested 1920×1200 at (0,0), measured
  2880×1800 physical at (0,0) — exactly fullscreen — unchanged at T+1.2 s and T+8.5 s.
- **No retiling of anything else**: zero other windows changed rect while it was up, and
  zero differed between before and after it closed.
- **Focus behaves**: it took the foreground itself (`GetForegroundWindow` == its own hwnd at
  both checkpoints), and on close the foreground returned to the previously focused window.

Escalation paths (`applications.json` float rule, manual `SetWindowLongPtrW` ex-style) were
therefore never needed and are not implemented. Stage 8's live run re-confirms this with the
real app under the real hotkey.
