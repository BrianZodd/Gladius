# Gladius

A keyboard-driven wallpaper picker overlay for Windows — a faithful port of
[hyprquickpaper](https://github.com/iamsurjog/hyprquickpaper) to PySide6. Press a hotkey,
scroll a strip of wallpaper thumbnails with vim keys, hit Enter, done.

> **Status**: pre-v1 — under construction. This README fills out as v1 lands.

## Run it locally

```
pip install PySide6
python gladius.py
```

`gladius.py --random` sets a random wallpaper with no UI.

Configuration auto-creates at `%APPDATA%\Gladius\config.json` on first run.

## Documentation

The source of truth lives in the repo:

| Doc | What it holds |
|---|---|
| `CLAUDE.md` | Project memory + how-we-work doctrine (loaded every session) |
| `ROADMAP.md` | The living roadmap + current focus / session handoff |
| `ARCHIVE.md` | Retired detail (section-scoped) |
| `DECISIONS.md` | What changed & why (section-scoped) |
| `AGENTS.md` | Routing for AI tools → read `CLAUDE.md` first |
| `README.md` | This file |

## Credits & license

Behavior and look inspired by [hyprquickpaper](https://github.com/iamsurjog/hyprquickpaper)
by iamsurjog — an original reimplementation, no code shared. MIT licensed.
