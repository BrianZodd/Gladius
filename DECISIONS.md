# Gladius — Decisions Log

The append-only ledger of *what changed and why* — project substance (product / schema / architecture / behavior) whose rationale isn't visible in the code. Methodology / how-we-work changes don't go here; they self-document in place, and the commit is their timeline.

> **Section-scoped.** To pull one entry, grep its dated header and read that slice — don't load the whole file. Entries are chronological.

## Index
- 2026-08-20 — Founding design calls (forge session)

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
