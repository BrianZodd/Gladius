"""Generate packaging/gladius.ico.

    python packaging/make_icon.py

The mark is taken from the app rather than invented: three tiles sheared by the
same -0.25 the strip uses, with the middle one "selected" in the default border
colour. At a glance it reads as the overlay itself.

Writes a real multi-resolution .ico (16-256 px) by assembling PNG-compressed
entries, which Windows has accepted since Vista. Qt can write .ico directly but
only at a single size, and a 256 px icon downscaled to the 16 px taskbar slot
looks like mud.

Re-run after changing the design; the result is committed, so a build never
depends on this script.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

# Must be set before Qt initialises: this script only ever paints onto a QImage,
# and asking for a real window system would fail outright in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPolygonF

OUT = Path(__file__).resolve().parent / "gladius.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

BG = QColor("#1B1B1F")          # near-black, so it reads on light and dark taskbars
ACCENT = QColor("#C27B63")      # the app's default selection border
TILE = QColor("#4A4A52")        # unselected tiles
SHEAR = -0.25                   # StripView's SHEAR_X


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)

    # rounded backdrop
    radius = size * 0.22
    p.setPen(Qt.NoPen)
    p.setBrush(BG)
    p.drawRoundedRect(0, 0, size, size, radius, radius)

    # three sheared tiles, centre one selected
    tile_w = size * 0.20
    gap = size * 0.07
    tile_h = size * 0.42
    top = (size - tile_h) / 2
    total = tile_w * 3 + gap * 2
    left = (size - total) / 2
    lean = tile_h * SHEAR

    for i in range(3):
        x = left + i * (tile_w + gap)
        # Matches the strip: Qt's shear(-0.25, 0) is x' = x - 0.25y, so the bottom
        # edge slides left and the top edge sits to its right.
        poly = QPolygonF([
            QPointF(x + lean / 2, top + tile_h),
            QPointF(x - lean / 2, top),
            QPointF(x + tile_w - lean / 2, top),
            QPointF(x + tile_w + lean / 2, top + tile_h),
        ])
        p.setBrush(ACCENT if i == 1 else TILE)
        p.drawPolygon(poly)

    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    # `ba` must stay referenced: QBuffer does not own it, and handing in a
    # temporary QByteArray segfaults once Python collects it mid-write.
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def write_ico(path: Path, images: list[QImage]) -> None:
    """ICONDIR + ICONDIRENTRY per image, each payload a PNG."""
    payloads = [png_bytes(i) for i in images]
    header = struct.pack("<HHH", 0, 1, len(images))     # reserved, type=icon, count
    offset = len(header) + 16 * len(images)

    entries, blob = b"", b""
    for img, data in zip(images, payloads):
        w = 0 if img.width() >= 256 else img.width()    # 0 means 256 in the ICO format
        h = 0 if img.height() >= 256 else img.height()
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        blob += data
        offset += len(data)

    path.write_bytes(header + entries + blob)


def main() -> int:
    _app = QGuiApplication([])      # QPainter needs a live Qt app, even offscreen

    images = [render(s) for s in SIZES]
    write_ico(OUT, images)
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes, sizes: "
          f"{', '.join(str(s) for s in SIZES)})")

    preview = OUT.with_name("icon-preview-256.png")
    images[-1].save(str(preview), "PNG")
    print(f"preview: {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
