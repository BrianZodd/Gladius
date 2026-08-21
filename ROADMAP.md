# Gladius — Roadmap

## Index
- **Current focus** — session handoff: where we are, what's next
- **Mission & phases** — the arc from plan to public release
- **Active to-dos** — loose items not yet in a phase
- **Pre-release gate** — what must be true before the repo goes public

---

## Current focus

*(2026-08-20 — v1 build session)*

- **Done this session**: all blueprint stages executed — `gladius.py` built bottom-up
  (config → scan/cache → Win32 setter → CLI → strip → overlay → settings pane), live
  acceptance passed under running komorebi, MIT `LICENSE` added and `README.md` completed
  for a stranger, planning scaffolds distilled into ARCHIVE.md / DECISIONS.md and deleted.
  Then the **whole distribution path**: `__version__` + a non-blocking update check (47
  tests green), a PyInstaller onedir build measured at 0.26 s startup, winget + Scoop
  manifests (winget-validated), and a tag-driven release workflow.
- **Next step**: **shakedown testing** — live with the app under the real `alt + w` binding
  and shake out what a scripted acceptance run cannot reach (feel of the scrolling, odd
  wallpapers, day-to-day annoyances). Public release is explicitly gated behind this; the
  pre-release gate below comes after, not before.
- **Open / needs user**: nothing blocking. Deferred until the public push is actually on
  the table: `SPEC.md` and `BLUEPRINT.md` are gone from the tree but survive in git
  history carrying machine paths (12 hits, confined to those two files), so history wants
  a squash or rewrite before the repo is flipped public.
- **Gotchas**: whkd reads its config at startup only (restart after editing whkdrc);
  wallpapers live in **subfolders** (the scan is recursive by design); MSIX-packaged
  Python hosts redirect `%LOCALAPPDATA%` writes, so the wallpaper path is resolved to a
  real location before it reaches `SystemParametersInfoW`.
- **Git**: `main`, pushed to `origin` = **github.com/BrianZodd/Gladius (private)**. Release
  workflow proven green via `workflow_dispatch`; no tag cut yet.
- **Blueprint**: complete — stages 0–9 all shipped. (Stage R verdicts: acrylic = WCA
  attempt B; komorebi = `Qt.Tool` alone passes — method and measurements in ARCHIVE.md.)

## Mission & phases

Ship a polished, faithful Windows port of hyprquickpaper, then keep it healthy.

1. **Plan** — forge spec, scaffold docs, write blueprint. ✅ 2026-08-20
2. **Build v1** — `gladius.py` per spec: config, cache, settings pane, `--random`,
   whkd + komorebi integration. ✅ 2026-08-20
3. **Live acceptance** — acceptance checklist on the real machine; komorebi outcome logged
   in DECISIONS.md. ✅ 2026-08-20
4. **Shakedown** — real-world use on the daily driver; fix what only living with it reveals.
   *(current phase — gates release, added 2026-08-20)*
5. **Public release** — pre-release gate below (incl. history rewrite), repo → public.
6. **Maintenance** — bug fixes only; feature ideas park in Active to-dos.

## Active to-dos

- *(v2 candidates, not commitments)*: live wallpaper preview while scrolling (debounced,
  Esc-restore) · per-monitor wallpapers via `IDesktopWallpaper` COM · grid layout mode ·
  fade transition on set.

- **Live-wallpaper engine compatibility** *(post-v1, wanted — raised 2026-08-20)*. Let
  Gladius browse and set wallpapers belonging to the animated-wallpaper apps people already
  run, instead of only static image files:
  - **Lively Wallpaper** (open source) — has a CLI (`Lively.exe`/`livelycu`) for setting a
    wallpaper and a per-wallpaper library folder with metadata; the most tractable first
    target.
  - **Wallpaper Engine** (Steam, paid, by far the largest install base) — controllable via
    its command-line interface (`wallpaper32.exe -control openWallpaper -file …`), with a
    Steam Workshop content folder to enumerate.
  - **Sucrose Wallpaper Engine** (open source) — same shape: local library + control surface.
  - Shape of the work: detect which engines are installed, enumerate each library, show
    their entries in the same strip (preview image per entry), and delegate the *set* to
    that engine rather than to `SystemParametersInfoW`. Note the existing
    `on_select_command` config key already covers the crude version of this for a single
    engine — the feature is really auto-detection plus mixed-source browsing.
  - Design question to settle first: one merged strip of everything, or a source filter/
    toggle? Affects the footer, the counter, and the config schema.

## Pre-release gate

Before flipping the repo public:

Boxes stay unticked for a deliberate human pass; the note under each records what was
already verified, so the pass is a confirmation rather than a re-investigation.

- [ ] All acceptance criteria passed live (komorebi running, real hotkey).
      → *Done 2026-08-20 — outcome logged in DECISIONS.md, evidence kept in ARCHIVE.md
      (0.30 s warm launch, format matrix confirmed against `TranscodedImageCache`).*
- [ ] `LICENSE` (MIT) present; README complete for a stranger (install, keys, config
      reference, whkd/komorebi guide, hyprquickpaper credit).
      → *Done — README's config table checked key-by-key against `Config` in `gladius.py`.*
- [ ] Grep-audit: no **machine-specific** data in tracked files **or git history**.
      → *Two different things, worth not confusing:*
      *(a) **Publisher identity is intended to be public** — `BrianZodd` and `Brian Gomez`
      now appear on purpose in `LICENSE`, the winget manifests, the version resource and
      every install URL. A published package has an author; these are not leaks.*
      *(b) **Machine paths must be zero.** `git grep -inE "UserData|Projects|C:\\Users"`
      over the tracked tree returns nothing.*
      → ***Git history is still NOT clean*** *— the planning commit carries `SPEC.md` and
      `BLUEPRINT.md` with 12 machine-path references. This is the one real item left;
      rewrite or squash before flipping public.*
- [ ] Temporary scaffolds distilled and deleted.
      → *Done — removed in `stage 9`; their essence lives in ARCHIVE.md / DECISIONS.md.*
- [ ] A fresh-machine smoke test: unzip the built bundle on a second machine and run it —
      works with zero edits.
      → *Dry-run review passed: no absolute paths in `gladius.py`, every directory resolves
      through `%APPDATA%`/`%LOCALAPPDATA%` + `SHGetKnownFolderPath`. The packaged exe was
      smoke-tested here (`--version`, `--config`, `--check-updates` all correct), but an
      actual run on a machine without Python is still untested — that is the one real gap.*
- [ ] Distribution wired end to end.
      → *Done — build script, release workflow, winget manifests (`winget validate` →
      succeeded), Scoop bucket, and the in-app update check. Nothing here can be finished
      remotely until the repo is public; see the release sequence below.*

## Release-day sequence

Already done: the repo exists at **github.com/BrianZodd/Gladius (private)**, `main` is
pushed, and the release workflow has been proven green twice via `workflow_dispatch` —
tests, build, exe smoke-test and a 46 MB artifact, matching the local build. No code work
remains; everything below is blocked purely on the shakedown finishing.

1. **Rewrite history** if that is the chosen route (see the grep-audit box) — far cheaper
   now than after anyone has cloned it.
2. **Flip public.**
3. **Tag `v1.0.0` and push it.** CI then runs the tag-gated half it has not yet exercised:
   the version/tag match check, `gh release create` with the zip + `.sha256`, and the
   commit of `bucket/gladius.json`. Watch this run — it is the only part never tested,
   because a tag build cannot be rehearsed without cutting a release.
4. **Verify the two install routes for real**: `scoop bucket add gladius
   https://github.com/BrianZodd/Gladius && scoop install gladius/gladius`, and confirm the
   zip downloads and runs from the releases page.
5. **Submit the winget PR** — `wingetcreate submit dist/manifests/winget` (details in
   `packaging/RELEASING.md`). The only step gated on someone else's review.
