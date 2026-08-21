# Gladius — Project Memory

## Index
- **Pitch & status** — what Gladius is, where the project stands
- **Stack & layout** — languages, deps, where things live
- **Documentation system** — the six-doc instance for this repo
- **Invariants** — the non-negotiables checked before any plan

---

## Pitch & status

**Gladius** is a keyboard-driven wallpaper picker overlay for Windows — a faithful PySide6
port of [hyprquickpaper](https://github.com/iamsurjog/hyprquickpaper) (Linux/Wayland). Hotkey
→ fullscreen translucent overlay → horizontal strip of wallpaper thumbnails → vim-key scroll
→ pick → wallpaper set via Win32 → app exits. Free and open source (MIT); repo private for
now, public later. Short build, then maintenance-only.

**Status**: v1 shipped 2026-08-20 — built, live-tested under komorebi, maintenance mode.
`gladius.py` (~860 lines) + `test_gladius.py` (28 tests). The planning scaffolds (`SPEC.md`,
`BLUEPRINT.md`, `RESEARCH-notes.md`) have self-destructed per their headers; their essence is
in ARCHIVE.md and DECISIONS.md. Remaining before the repo goes public: the pre-release gate
in ROADMAP.md.

## Stack & layout

- Python 3.12 + PySide6 (only dependency); single-file app `gladius.py`. Tests are stdlib
  `unittest` in `test_gladius.py` — `python -m unittest test_gladius -v`.
- User config auto-creates at `%APPDATA%\Gladius\config.json`; thumbnail cache and transcode
  scratch under `%LOCALAPPDATA%\Gladius\`. Nothing user-specific is committed.
- Host integration (dev machine): whkd hotkey `alt + w` in `~/.config/whkdrc` (whkd reads
  config at startup only — restart it after edits); komorebi kept away via the `Qt.Tool`
  window flag, `~/applications.json` float rule as tested fallback.

## Documentation system

This repo runs the Nova six-doc system (`nova-documentation` skill is the method): CLAUDE.md
(this file, lean, always loaded) · ROADMAP.md (current focus + phases + pre-release gate) ·
ARCHIVE.md + DECISIONS.md (section-scoped) · AGENTS.md · README.md (public landing page).
Links are kept minimal in lieu of a `check-links` npm gate — this is a Python repo staying
free of Node tooling.

**Where v1's history lives**: design reference and build/measurement record → ARCHIVE.md
(2026-08-20 sections); why each call was made → DECISIONS.md. Read the section, not the file.

## Invariants

1. **Nothing machine-specific is committed.** User config lives in `%APPDATA%\Gladius\`,
   generated files in `%LOCALAPPDATA%\Gladius\`; the repo must work verbatim for a stranger.
2. **Single-file app, single dependency.** `gladius.py` + stdlib + PySide6. Any new file or
   dependency needs a DECISIONS.md entry first.
3. **No code reuse from hyprquickpaper** — it has no license file. Lessons and behavior
   parity only; every line here is original.
4. **The wallpaper folder is read-only to Gladius.** Never write, move, or rename anything
   inside it.
5. **Registry writes are limited** to the fit-mode keys under `HKCU\Control Panel\Desktop`
   (`WallpaperStyle`, `TileWallpaper`).
6. **"Done" means the live acceptance run passed** — the checklist in ROADMAP.md's
   pre-release gate (from SPEC §9), executed on the real machine under running komorebi,
   not just unit-level checks.
