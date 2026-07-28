"""Builds assets/unpaster.ico from the drawn tray icon.

Qt writes PNG but not ICO, so the ICO container is assembled here: a 6-byte
header, one 16-byte directory entry per frame, then the PNG frames.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer
from PySide6.QtWidgets import QApplication

from unpaster.ui.icon import tray_pixmap

SIZES = [16, 24, 32, 48, 64, 128, 256]
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "unpaster.ico"


def _png_bytes(size: int) -> bytes:
    # QBuffer keeps its own byte array; passing a temporary QByteArray would
    # leave the buffer pointing at freed memory.
    buffer = QBuffer()
    buffer.open(QBuffer.WriteOnly)
    tray_pixmap(size).save(buffer, "PNG")
    buffer.close()
    return bytes(buffer.data())


def build_ico(sizes: list[int]) -> bytes:
    frames = [_png_bytes(size) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(frames))

    offset = len(header) + 16 * len(frames)
    entries = b""
    for size, frame in zip(sizes, frames):
        dimension = size % 256  # 256 is written as 0
        entries += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32,
                               len(frame), offset)
        offset += len(frame)

    return header + entries + b"".join(frames)


def main() -> None:
    app = QApplication(sys.argv)  # a QGuiApplication must exist to paint
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(build_ico(SIZES))
    print(f"wrote {OUTPUT}")
    del app


if __name__ == "__main__":
    main()
