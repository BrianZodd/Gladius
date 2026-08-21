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
  (config → scan/cache → Win32 setter → CLI → strip → overlay → settings pane), 28 stdlib
  `unittest` tests green, live acceptance passed under running komorebi, MIT `LICENSE`
  added and `README.md` completed for a stranger. The three planning scaffolds were
  distilled into ARCHIVE.md / DECISIONS.md and deleted per their headers.
- **Next step**: the pre-release gate below — a pass over the five boxes, then flip the
  repo public. Nothing in the code is blocking it.
- **Open / needs user**: whether to squash history before going public. `SPEC.md` and
  `BLUEPRINT.md` are deleted from the tree but remain in git history, and they carry
  personal references (see the grep-audit box).
- **Gotchas**: whkd reads its config at startup only (restart after editing whkdrc);
  wallpapers live in **subfolders** (the scan is recursive by design); MSIX-packaged
  Python hosts redirect `%LOCALAPPDATA%` writes, so the wallpaper path is resolved to a
  real location before it reaches `SystemParametersInfoW`.
- **Git**: `main`, no remote yet. v1 tip = `stage 9: license + public-facing docs`.
- **Blueprint**: complete — stages 0–9 all shipped. (Stage R verdicts: acrylic = WCA
  attempt B; komorebi = `Qt.Tool` alone passes — method and measurements in ARCHIVE.md.)

## Mission & phases

Ship a polished, faithful Windows port of hyprquickpaper, then keep it healthy.

1. **Plan** — forge spec, scaffold docs, write blueprint. ✅ 2026-08-20
2. **Build v1** — `gladius.py` per spec: config, cache, settings pane, `--random`,
   whkd + komorebi integration. ✅ 2026-08-20
3. **Live acceptance** — acceptance checklist on the real machine; komorebi outcome logged
   in DECISIONS.md. ✅ 2026-08-20
4. **Public release** — pre-release gate below, repo → public.
5. **Maintenance** — bug fixes only; feature ideas park in Active to-dos.

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
- [ ] Grep-audit: no personal data anywhere in tracked files **or git history**.
      → *Tracked tree is clean: `gladius.py`, `test_gladius.py`, `README.md` and
      `AGENTS.md` have zero hits; the remainder sit in `LICENSE` (copyright) and the
      private-history docs. **Git history is NOT clean** — the planning commit still
      carries `SPEC.md`/`BLUEPRINT.md` with personal references. Squash or rewrite
      history before flipping public.*
- [ ] Temporary scaffolds distilled and deleted.
      → *Done — removed in `stage 9`; their essence lives in ARCHIVE.md / DECISIONS.md.*
- [ ] A fresh-machine smoke test: clean clone + `pip install PySide6` + run — works with
      zero repo edits.
      → *Dry-run review passed: no absolute paths in `gladius.py`, every directory resolves
      through `%APPDATA%`/`%LOCALAPPDATA%` + `SHGetKnownFolderPath`. An actual run on a
      second machine is still untested.*
