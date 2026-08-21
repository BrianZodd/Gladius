# Releasing Gladius

Everything a release needs, in order. The short version: **bump the version, push a
tag, submit the winget manifest.** CI does the rest.

---

## What a user actually gets

One artifact serves every channel — a zipped [PyInstaller](https://pyinstaller.org)
*onedir* bundle, `gladius-<version>-win64.zip` (~46 MB):

| Route | What happens |
|---|---|
| `winget install BrianZodd.Gladius` | winget unpacks the zip and registers `gladius` as a portable command |
| `scoop install gladius` | Scoop unpacks it, shims `gladius.exe`, adds a Start-menu shortcut |
| **UniGetUI** | shows Gladius through whichever of the two is installed — no extra packaging |
| Releases page | download the zip, unzip anywhere, run `gladius.exe` |

Nothing writes to `Program Files` and nothing needs admin. Gladius is a launcher you
bind to a hotkey, so "portable" is the honest shape — uninstalling is deleting the
folder (plus `%APPDATA%\Gladius` and `%LOCALAPPDATA%\Gladius` if you want the config
and thumbnail cache gone too).

**Onedir, never onefile.** PyInstaller's onefile mode unpacks the entire bundle to a
temp folder on *every* launch — seconds, at PySide6's size. Gladius exists to appear
instantly under a hotkey, so onefile is disqualified on principle. Measured on the
development machine: the onedir exe starts in **0.26 s**, slightly *faster* than
running `gladius.py` directly (0.33 s), against a 1.5 s budget.

---

## Cutting a release

1. **Bump the version.** `__version__` in `gladius.py` is the single source of truth —
   the build script, `--version`, the update check and both manifests all read from it.

2. **Commit and tag.** The tag must match `__version__`; CI checks this and fails the
   build if they disagree, before wasting time compiling.
   ```bash
   git commit -am "release: v1.1.0" && git tag v1.1.0 && git push origin main --tags
   ```

3. **CI takes over** (`.github/workflows/release.yml`): runs the tests, builds the
   bundle, smoke-tests that the built exe can report its own version, publishes the
   GitHub Release with the zip and its `.sha256`, then renders and commits
   `bucket/gladius.json` so Scoop users have the new version immediately.

4. **Submit the winget manifest.** This is the only step a human does, because it is a
   pull request against a repository Microsoft owns. Download the `winget-manifests`
   artifact from the workflow run, or render it locally:
   ```bash
   python packaging/render_manifests.py --from-dist
   winget validate --manifest dist/manifests/winget
   ```
   Then submit with [wingetcreate](https://github.com/microsoft/winget-create):
   ```bash
   wingetcreate submit --token <gh-token> dist/manifests/winget
   ```
   Expect a bot to run validation on the PR, then a human review. Nothing on our side
   is blocked while it sits.

---

## One-time setup

- **Scoop bucket** — lives in this repo under `bucket/`, so there is no second repo to
  maintain. Users add it with:
  ```bash
  scoop bucket add gladius https://github.com/BrianZodd/Gladius
  scoop install gladius/gladius
  ```
  Requires the repo to be public. The manifest carries `checkver`/`autoupdate`, so
  `scoop update` finds new versions on its own.

- **winget** — the first submission creates `manifests/b/BrianZodd/Gladius/` in
  [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs). Later versions are
  the same `wingetcreate submit` against a new version folder.

- **GitHub token scope** — pushing `.github/workflows/` needs the `workflow` scope:
  ```bash
  gh auth refresh -s workflow
  ```

---

## Building locally

```bash
pip install -r requirements.txt -r requirements-dev.txt
python packaging/build.py
```

Outputs `dist/gladius/` (the bundle), the zip, and the `.sha256`. `dist/` and `build/`
are gitignored.

To check a manifest without publishing anything:
```bash
python packaging/render_manifests.py --from-dist
winget validate --manifest dist/manifests/winget
```

---

## How updating works from the user's side

`gladius.py` checks GitHub's releases API for a newer tag, but **never on the launch
path** — the overlay reads a small cached JSON file, and the network refresh runs on the
thread pool after the window is already visible, at most once a day. So the check can
only ever affect the *next* launch, and the 0.26 s startup is untouched.

When a newer version is cached, the footer gains a quiet note naming the right command
for how that copy was installed — `scoop update gladius`, `winget upgrade
BrianZodd.Gladius`, or the releases page for a manual unzip. Gladius never updates
itself: replacing a running executable on Windows fights file locks, and the package
manager that installed it already does this correctly.

`gladius --check-updates` forces a synchronous check for anyone who wants one.
