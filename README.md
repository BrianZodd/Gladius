# Gladius

A keyboard-driven wallpaper picker for Windows.

Press a hotkey, and a translucent overlay drops over everything: a horizontal strip of your
wallpapers, sheared into leaning parallelograms. Scroll it with vim keys, hit `Space`, and the
wallpaper changes and the app is gone. No tray icon, no daemon, no window to manage — it lives
for a few seconds at a time.

Gladius is a faithful Windows port of
[hyprquickpaper](https://github.com/iamsurjog/hyprquickpaper) (Hyprland/Wayland). Same look,
same keys, same idea — rewritten from scratch in Python + PySide6, with the original's three
best-known papercuts fixed. One file, one dependency, MIT licensed.

```
pip install PySide6
python gladius.py
```

## Requirements

Windows 10 or 11. That's it — the packaged build bundles its own Python and PySide6.
(Running from source instead needs Python 3.10+; see below.)

## Install

Pick whichever you already use. All of them leave you with a `gladius` command.

**winget**

```bash
winget install BrianZodd.Gladius
```

**Scoop**

```bash
scoop bucket add gladius https://github.com/BrianZodd/Gladius
scoop install gladius/gladius
```

**[UniGetUI](https://www.marticliment.com/unigetui/)** — search for *Gladius* and install
it from there; it shows up through whichever of winget or Scoop you have enabled.

**Manual** — download `gladius-<version>-win64.zip` from the
[releases page](https://github.com/BrianZodd/Gladius/releases/latest), unzip it anywhere,
and run `gladius.exe`. Nothing goes into `Program Files` and nothing needs admin —
uninstalling is deleting the folder.

**From source** — needs Python 3.10 or newer:

```bash
git clone https://github.com/BrianZodd/Gladius.git
cd Gladius
pip install -r requirements.txt
python gladius.py
```

From source, launch with **`pythonw.exe`** rather than `python.exe` so no console window
flashes on screen. The packaged `gladius.exe` already behaves that way.

On first run Gladius creates `%APPDATA%\Gladius\config.json` with defaults and points
`wallpaper_path` at `<your Pictures folder>\Wallpapers`. If your wallpapers live somewhere
else, edit that one value — `gladius --config` prints the path to the file.

## Updating

If you installed through a package manager, update the normal way — `winget upgrade
BrianZodd.Gladius` or `scoop update gladius` — or press Update in UniGetUI.

Gladius checks GitHub for a newer release at most once a day, and when one exists the
footer quietly tells you, naming the exact command for how your copy was installed. The
check never happens on the launch path: the overlay reads a small cached file, and the
network request runs in the background *after* the window is already up, so it can only
affect the next launch. `gladius --check-updates` forces a check.

Gladius never updates itself — swapping out a running executable on Windows is a good way
to corrupt an install, and your package manager already does it properly.

## Keys

| Key | Action |
|---|---|
| `J` / `→` | next wallpaper |
| `K` / `←` | previous wallpaper |
| `D` | forward one screenful |
| `U` | back one screenful |
| `Space` / `Enter` | set the wallpaper and exit |
| `Esc` | exit, changing nothing |
| `S` | open/close the settings panel |

Mouse works too: the wheel and click-drag scroll the strip, and a click on a tile selects and
sets it.

**Settings panel** (`S`) — `J`/`K` (or `↑`/`↓`) move between rows, `H`/`L` (or `←`/`→`) change
the value, `Esc` or `S` closes it. Every change applies to the overlay immediately *and* is
written straight to `config.json`, so it survives the next launch.

## Command line

| Command | What it does |
|---|---|
| `gladius` | open the picker overlay |
| `gladius --random` | set a random wallpaper and exit — no window at all |
| `gladius --config` | print the path to your config file |
| `gladius --version` | print the version |
| `gladius --check-updates` | check for a newer release right now |

*(From source, that's `python gladius.py --random` and so on.)*

Launching a second time while the overlay is open does nothing, so a mashed hotkey can't stack
overlays.

## Configuration

`%APPDATA%\Gladius\config.json`. Every key is optional — anything missing, unknown, or
unusable falls back to its default rather than failing to launch.

| Key | Default | Meaning |
|---|---|---|
| `wallpaper_path` | `<Pictures>\Wallpapers` | folder to read wallpapers from |
| `recursive` | `true` | include subfolders |
| `number_of_pictures` | `7` | tiles visible at once (3–15); also the `D`/`U` jump size |
| `border_color` | `"#C27B63"` | selection border — any colour Qt understands (`"#RRGGBB"`, `"#RGB"`, or a name like `"steelblue"`) |
| `backdrop` | `"dim"` | `"dim"` or `"acrylic"` (Windows blur-behind) |
| `dim_opacity` | `0.7` | how dark the dim backdrop is, `0.0`–`1.0` |
| `shear` | `true` | lean the tiles into parallelograms, like the original |
| `fit_mode` | `"fill"` | `fill`, `fit`, `span`, `stretch`, `center`, `tile` |
| `cache_batch_size` | `8` | thumbnail worker threads |
| `on_select_command` | `null` | run this instead of setting the wallpaper; `{path}` is replaced with the image path |

`on_select_command` is the escape hatch for anyone who wants something else to handle the
wallpaper — a theming tool, a script, another wallpaper engine:

```json
"on_select_command": "wal -i \"{path}\""
```

Supported image formats: `.jpg` `.jpeg` `.jfif` `.png` `.bmp` `.webp` `.gif` `.avif`.
Windows itself can't set the last few, so Gladius quietly converts those to PNG in
`%LOCALAPPDATA%\Gladius\set\` and sets that instead — from your side it just works.

## Hotkey setup

Gladius is a launcher, so bind it to whatever hotkey daemon you already run.

**[whkd](https://github.com/LGUG2Z/whkd)** — add to `~/.config/whkdrc`:

```
alt + w : & 'C:\path\to\gladius.exe'
```

> whkd reads its config **only at startup** — restart whkd after editing, or the binding
> won't exist.

**Windows shortcut** — make a shortcut whose target is `C:\path\to\gladius.exe`, then set a
shortcut key in its properties.

**Wallpaper rotation at logon** — Task Scheduler, trigger *At log on*, action
`"C:\path\to\gladius.exe" --random`. `--random` never opens a window or a dialog, so it's
safe to run unattended.

*(Running from source? Substitute `'C:\path\to\pythonw.exe' 'C:\path\to\gladius.py'` for
`gladius.exe` in any of the above — `pythonw` is what keeps a console from flashing.)*

To find where a package manager put the exe: `scoop which gladius`, or
`winget list BrianZodd.Gladius` and look under
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\`.

## Tiling window managers

Gladius creates its overlay as a tool window (`WS_EX_TOOLWINDOW`), which tiling window
managers skip by design — it floats above your layout instead of being tiled into it.

Verified against [komorebi](https://github.com/LGUG2Z/komorebi): the overlay keeps its exact
fullscreen geometry, nothing else on screen gets retiled, and focus returns to the window you
were using when it closes. **No float rule or config change is needed** — if your window
manager does try to manage it, that's a bug worth reporting.

## What's different from hyprquickpaper

Behaviour is a faithful port. Three things were deliberately changed, all fixes for issues the
original documents in its own README:

- **Thumbnails can't go stale.** The cache is keyed by path + modification time + size, so
  renaming or editing an image regenerates its thumbnail instead of showing the old one.
- **No blank first run.** Thumbnails are generated in-process and each tile repaints the
  moment its own thumbnail lands, so a cold start shows placeholders filling in live rather
  than an empty strip until you restart.
- **Subfolders can't collide.** Cache keys are hashes of the full path, so two images with the
  same filename in different folders can't overwrite each other's thumbnails.

One small addition: the selection starts on your *current* wallpaper when it's in the folder,
rather than always at the first tile.

## Notes on odd setups

Gladius tries hard to work on machines that aren't the one it was written on.

- **Any resolution and DPI.** Tile size and thumbnail resolution scale to the display, so it
  stays sharp on a 4K or high-DPI panel and still lays out sensibly on a small laptop screen.
- **Redirected user folders.** The Pictures folder is resolved through the Windows known-folder
  API, so it finds the real location even if you've moved your user folders off `C:\Users`.
- **Microsoft Store Python** (and other MSIX-packaged hosts) redirect writes under
  `%LOCALAPPDATA%` into a private per-package store that Explorer can't read. Gladius resolves
  the wallpaper path before handing it to Windows, so converted images still apply. If you hit
  anything else odd under Store Python, a regular python.org install is the smoother road.
- **Locked-down machines.** If policy blocks the registry write, you lose the fit-mode setting,
  not the wallpaper. If the thumbnail cache folder isn't writable, you get placeholder tiles
  instead of a crash.
- **Nothing to find?** If the wallpaper folder is empty or missing, Gladius says so in a dialog
  naming the folder and your config file — it won't just silently fail to appear.

## Repo layout

Everything runs from `gladius.py` — a single file, plus a stdlib `unittest` suite:

```
gladius.py           the entire application
test_gladius.py      unit tests:  python -m unittest test_gladius -v
requirements.txt     PySide6
requirements-dev.txt PyInstaller — build time only
packaging/           build script, release runbook, winget + Scoop manifests
bucket/              the Scoop bucket for this app
```

Building the distributable yourself: see [packaging/RELEASING.md](packaging/RELEASING.md).

The project's own documentation lives in the repo:

| Doc | What it holds |
|---|---|
| `CLAUDE.md` | project memory + working doctrine (loaded by AI tools every session) |
| `ROADMAP.md` | current focus, phases, and what's parked for later |
| `DECISIONS.md` | what changed and why — the reasoning behind the design |
| `ARCHIVE.md` | retired detail kept for reference |
| `AGENTS.md` | routing for AI tools → read `CLAUDE.md` first |
| `README.md` | this file |

## Credits & license

Look, keys, and behaviour follow [hyprquickpaper](https://github.com/iamsurjog/hyprquickpaper)
by [iamsurjog](https://github.com/iamsurjog) — full credit for the idea and the design. This is
an original reimplementation for Windows: no code is shared between the projects.

MIT — see [LICENSE](LICENSE).
