# Gladius — Roadmap

## Index
- **Current focus** — session handoff: where we are, what's next
- **Mission & phases** — the arc from plan to public release
- **Active to-dos** — loose items not yet in a phase
- **Pre-release gate** — what must be true before the repo goes public

---

## Current focus

*(2026-08-20 — planning session)*

- **Done this session**: prior-art sweep of hyprquickpaper (no license → lessons only);
  design forged and approved (`SPEC.md`); six-doc system scaffolded; execution plan written
  (`BLUEPRINT.md`) for a fresh Opus session.
- **Next step**: fresh session executes `BLUEPRINT.md` stage by stage (build → integrate →
  live-test).
- **Open / needs user**: none — plan is self-contained.
- **Gotchas**: whkd reads its config at startup only (restart after editing whkdrc);
  komorebi runs elevated and will fight any managed window — `Qt.Tool` must be verified
  live; wallpapers live in **subfolders** (scan must be recursive).
- **Git**: repo initialized 2026-08-20; single planning commit on `main` (docs scaffold +
  SPEC.md + BLUEPRINT.md). No remote yet.
- **Blueprint**: BLUEPRINT.md — stage R/9 done (spikes: acrylic = WCA attempt B, komorebi =
  `Qt.Tool` alone passes), next: Stage 1.

## Mission & phases

Ship a polished, faithful Windows port of hyprquickpaper, then keep it healthy.

1. **Plan** — forge spec, scaffold docs, write blueprint. ✅ 2026-08-20
2. **Build v1** — execute BLUEPRINT.md: `gladius.py` per SPEC, config, cache, settings pane,
   `--random`, whkd + komorebi integration.
3. **Live acceptance** — SPEC §9 checklist on the real machine; log komorebi test outcome in
   DECISIONS.md.
4. **Public release** — pre-release gate below, repo → public.
5. **Maintenance** — bug fixes only; feature ideas park in Active to-dos.

## Active to-dos

- *(v2 candidates, not commitments)*: live wallpaper preview while scrolling (debounced,
  Esc-restore) · per-monitor wallpapers via `IDesktopWallpaper` COM · grid layout mode ·
  fade transition on set.

## Pre-release gate

Before flipping the repo public:

- [ ] All SPEC §9 acceptance criteria passed live (komorebi running, real hotkey).
- [ ] `LICENSE` (MIT) present; README complete for a stranger (install, keys, config
      reference, whkd/komorebi guide, hyprquickpaper credit).
- [ ] Grep-audit: no `Brian`, `UserData`, machine paths, or personal data anywhere in
      tracked files or git history (history is clean if this holds from commit one).
- [ ] Temporary scaffolds distilled and deleted (`SPEC.md`, `BLUEPRINT.md` per their
      headers).
- [ ] A fresh-machine smoke test (or honest dry-run review): clean clone + `pip install
      PySide6` + run — works with zero repo edits.
