# Gladius — Decisions Log

The append-only ledger of *what changed and why* — project substance (product / schema / architecture / behavior) whose rationale isn't visible in the code. Methodology / how-we-work changes don't go here; they self-document in place, and the commit is their timeline.

> **Section-scoped.** To pull one entry, grep its dated header and read that slice — don't load the whole file. Entries are chronological.

## Index
- 2026-08-20 — Founding design calls (forge session)
- 2026-08-20 — v1 build session (spike verdicts, production hardening, live acceptance)

---

## 2026-08-20 — Founding design calls (forge session)

Decisions from the nova-forge pass that shaped `SPEC.md`, with the trade-offs:

- **Horizontal strip, not a grid.** The original brief assumed hyprquickpaper was a grid;
  the source sweep showed it's a single sheared horizontal strip. Brian chose the faithful
  port over the (arguably more practical for 72 images) grid — fidelity to the original's
  identity is the product. Grid parks as a v2 candidate.
- **Select-only, no live preview.** Highlighting never touches the desktop; only
  Space/Enter sets. Avoids registry churn and restore-state logic; live preview parked v2.
- **In-overlay settings pane** (key `S`) rather than config-file-only or a separate window —
  one surface, keyboard-driven like everything else; writes through to config.json live.
- **No code reuse from the reference** — hyprquickpaper has no license file, so it's
  behavior-parity lessons only. Moot in practice (QML→Python rewrite) but binding (CLAUDE.md
  invariant 3).
- **Config in `%APPDATA%`, not the repo** — diverges from the original (config beside the
  QML). Required by the public-FOSS goal: the repo carries no user paths; first run
  self-creates defaults, resolving Pictures via `SHGetKnownFolderPath` because Brian's
  machines redirect user folders away from `%USERPROFILE%`.
- **Thumb cache keyed by `sha1(path|mtime|size)`**, recursive scan — deliberately breaks
  parity to fix three documented upstream bugs (stale thumbs, blank first run, basename
  collisions across subfolders).
- **komorebi strategy: `Qt.Tool` window flag primary**, `applications.json` float rule only
  as tested fallback — self-contained beats config-editing another tool; the live test
  decides, outcome to be logged here.
- **No DESIGN.md** — the design identity is "faithful reproduction of the original strip,"
  fully specified in SPEC §3; a seventh doc would be scaffolding for its own sake.

## 2026-08-20 — v1 build session (spike verdicts, production hardening, live acceptance)

### Runtime spike verdicts (Stage R — full method and measurements in RESEARCH-notes.md)

- **Acrylic = `SetWindowCompositionAttribute` (`ACCENT_ENABLE_ACRYLICBLURBEHIND`).** The
  documented Win11 `DWMWA_SYSTEMBACKDROP_TYPE` returns `S_OK` but paints a flat opaque grey
  panel on a frameless layered window — worse than the dim fallback — so the undocumented
  API wins on merit. Judged by measuring high-frequency image energy, not by return codes,
  precisely because the losing call *reports success*. Qt's `WA_TranslucentBackground`
  stays on. Tint lightened from the planned `0x99000000` to `0x30000000`, which was
  otherwise dark enough to hide the very blur it enables.
- **komorebi = `Qt.Tool` alone.** It yields `WS_EX_TOOLWINDOW`, which komorebi's window
  filter skips: geometry untouched, no retiling of other windows, focus taken and returned.
  The planned `applications.json` float-rule fallback is therefore *not* shipped — Gladius
  stays self-contained and edits no other tool's config.

### Production-compatibility hardening (added on request, mid-build)

Gladius is meant to be downloaded by strangers on hardware and Windows setups nothing like
the machine it was written on (heavily customised shells, Windhawk/StartAllBack, any DPI,
any locale). The build therefore added a hardening pass beyond the blueprint's feature
scope. Each item is a failure that would have been invisible here and fatal elsewhere:

- **Thumbnail height tracks the display** (60% of the tallest screen's device pixels,
  floor 500, ceiling 1600) and is **folded into the cache key**. A fixed 500px thumbnail
  upscales visibly on a 4K or high-DPI panel; keying by height means a different display
  gets its own entries rather than silently reusing thumbnails that are too small.
- **The config is treated as hostile input.** It is a hand-editable file driving an app
  launched by a hotkey with no console, so a bad value must degrade to a default rather
  than look like a broken hotkey. Every field is coerced (`"9"` → 9, `"off"` → False),
  ranges clamped, `fit_mode`/`backdrop` validated against their vocabularies, and
  `border_color` validated with Qt — which accepts any colour Qt can parse, so a custom
  value the settings pane never produces survives untouched.
- **Failures are visible.** Under `pythonw` there is no stderr anyone reads, so "no images
  found" now shows a dialog naming the folder *and* the config path to fix it. `--random`
  deliberately does **not** dialog: it may run unattended from a logon scheduled task,
  where a modal box would block forever.
- **`%APPDATA%`/`%LOCALAPPDATA%` are not assumed to exist** (fallback under `~/AppData`),
  known-folder resolution falls back instead of raising, and an unwritable cache directory
  degrades to placeholder tiles.
- **A restricted registry costs the fit mode, not the wallpaper**: `_apply_fit_mode`
  reports failure and the image is still set.
- **Paint-path geometry is guarded** so absurd window sizes cannot divide by zero — checked
  from 1×1 up to 3840×2160, plus ultrawide and netbook layouts.

### The wallpaper path handed to Windows is always resolved (found during acceptance)

`SystemParametersInfoW` does not read the image — Explorer does, from outside the calling
process. So the path must be real *outside* whatever sandbox Gladius happens to run in.
Under MSIX filesystem redirection (**Microsoft Store Python**, or any packaged host), a file
written to `%LOCALAPPDATA%` physically lands in a package-private store; the literal path
then resolves to nothing for Explorer. The call still returns success and the desktop
silently keeps the old wallpaper — a failure with no error anywhere.

This was caught because the build ran inside exactly such a container. Proof: identical PNG
bytes at two locations — the one under `%LOCALAPPDATA%` was ignored by Windows, the one
under a plain path was consumed; passing the *resolved* path made the redirected one work
too. `_spi_set` therefore resolves every path it hands to Windows. This only ever affects
the transcode output (webp/avif/gif and retry cases); direct-format sets were already
resolved. Cost: one `Path.resolve()`. Benefit: animated/exotic formats work for Store-Python
users instead of failing silently.
