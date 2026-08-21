"""Stamp the real version and SHA256 into the winget and Scoop manifests.

    python packaging/render_manifests.py --sha <sha256>          # version from gladius.py
    python packaging/render_manifests.py --from-dist             # read both from dist/

The manifests in `packaging/` are the source of truth for everything *except*
version and hash, which only exist once an artifact has actually been published.
Editing four files by hand is how a hash ends up matching three of them, so this
does the substitution in one place.

Writes the result to `dist/manifests/` — never over the templates, so the repo
copy stays a template and a bad render is thrown away by deleting a folder.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
OUT = ROOT / "dist" / "manifests"

PLACEHOLDER = "REPLACE_WITH_SHA256_OF_THE_PUBLISHED_ZIP"
OLD_VERSION = "1.0.0"          # the version literal sitting in the templates


def read_version() -> str:
    src = (ROOT / "gladius.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M)
    if not m:
        raise SystemExit("could not find __version__ in gladius.py")
    return m.group(1)


def sha_from_dist(version: str) -> str:
    f = ROOT / "dist" / f"gladius-{version}-win64.zip.sha256"
    if not f.exists():
        raise SystemExit(f"{f} not found — run packaging/build.py first")
    return f.read_text(encoding="utf-8").split()[0]


def render(version: str, sha: str) -> list[Path]:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
        raise SystemExit(f"that does not look like a sha256: {sha!r}")

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "winget").mkdir(parents=True)
    (OUT / "scoop").mkdir(parents=True)

    written = []
    for src in sorted((PACKAGING / "winget").glob("*.yaml")) + \
               sorted((PACKAGING / "scoop").glob("*.json")):
        text = src.read_text(encoding="utf-8")
        text = text.replace(PLACEHOLDER, sha.lower())
        if version != OLD_VERSION:
            text = text.replace(OLD_VERSION, version)
        dst = OUT / src.parent.name / src.name
        dst.write_text(text, encoding="utf-8")
        written.append(dst)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sha", help="sha256 of the published zip")
    ap.add_argument("--from-dist", action="store_true",
                    help="read the sha from dist/*.sha256")
    ap.add_argument("--version", help="override the version (default: gladius.py)")
    args = ap.parse_args()

    version = args.version or read_version()
    if args.from_dist:
        sha = sha_from_dist(version)
    elif args.sha:
        sha = args.sha
    else:
        ap.error("pass --sha <sha256> or --from-dist")

    for p in render(version, sha):
        print(p.relative_to(ROOT))
    print()
    print(f"version {version}, sha256 {sha.lower()}")
    print("winget: validate with  winget validate --manifest dist/manifests/winget")
    return 0


if __name__ == "__main__":
    sys.exit(main())
