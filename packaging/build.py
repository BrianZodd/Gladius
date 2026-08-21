"""Build the distributable Gladius bundle.

    python packaging/build.py

Produces, under `dist/`:
    gladius/                     the PyInstaller onedir bundle
    gladius-<version>-win64.zip  the release artifact
    gladius-<version>-win64.zip.sha256

Onedir, never onefile. Onefile unpacks the whole bundle to a temp folder on
*every* launch — seconds, with a payload as big as PySide6 — which would defeat
the point of an overlay you summon with a hotkey. Onedir starts about as fast as
running the .py directly, and the zip-of-a-folder shape is exactly what both
winget (zip + nested portable) and Scoop want.

Requires PyInstaller (`pip install pyinstaller`); everything else is stdlib.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
NAME = "gladius"


def read_version() -> str:
    """Parse __version__ out of gladius.py without importing it — importing
    would drag in PySide6 and Windows-only modules for no reason."""
    src = (ROOT / "gladius.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M)
    if not m:
        raise SystemExit("could not find __version__ in gladius.py")
    return m.group(1)


def write_version_file(version: str) -> Path:
    """Windows version resource. Without one, Properties → Details is blank and
    an unsigned exe looks that much more like something to be suspicious of."""
    parts = [int(x) for x in version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    quad = ", ".join(str(x) for x in parts[:4])

    BUILD.mkdir(parents=True, exist_ok=True)
    path = BUILD / "version_info.txt"
    path.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({quad}), prodvers=({quad}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Brian Gomez'),
      StringStruct('FileDescription', 'Gladius - keyboard-driven wallpaper picker'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'gladius'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 Brian Gomez. MIT licensed.'),
      StringStruct('OriginalFilename', 'gladius.exe'),
      StringStruct('ProductName', 'Gladius'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""", encoding="utf-8")
    return path


def run_pyinstaller(version: str) -> Path:
    icon = ROOT / "packaging" / "gladius.ico"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onedir",              # see the module docstring — never --onefile
        "--windowed",            # no console flash on a hotkey launch
        "--name", NAME,
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
        "--version-file", str(write_version_file(version)),
    ]
    if icon.exists():
        cmd += ["--icon", str(icon)]
    cmd.append(str(ROOT / "gladius.py"))

    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)

    out = DIST / NAME
    exe = out / f"{NAME}.exe"
    if not exe.exists():
        raise SystemExit(f"expected {exe} to exist after the build")
    return out


def make_zip(bundle: Path, version: str) -> Path:
    """Zip the bundle with a `gladius/` prefix, so extraction always lands in a
    folder rather than spraying ~200 files into the user's Downloads."""
    zip_path = DIST / f"{NAME}-{version}-win64.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(bundle.rglob("*")):
            if f.is_file():
                z.write(f, Path(NAME) / f.relative_to(bundle))
    return zip_path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if shutil.which("git") and not (ROOT / "gladius.py").exists():
        raise SystemExit("run this from the repo root")

    version = read_version()
    print(f"building gladius {version}")

    bundle = run_pyinstaller(version)
    zip_path = make_zip(bundle, version)
    digest = sha256(zip_path)
    (DIST / f"{zip_path.name}.sha256").write_text(
        f"{digest}  {zip_path.name}\n", encoding="utf-8")

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print()
    print(f"  version : {version}")
    print(f"  zip     : {zip_path}  ({size_mb:.1f} MB)")
    print(f"  sha256  : {digest}")
    print()
    print("Manifest values — paste these into the winget/Scoop manifests:")
    print(f"  InstallerSha256 / hash : {digest}")
    print(f"  url  : https://github.com/BrianZodd/Gladius/releases/download/"
          f"v{version}/{zip_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
