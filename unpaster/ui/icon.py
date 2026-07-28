"""Tray icon drawn in code so the project ships no binary assets.

The glyph is a path rather than text: Qt's offscreen platform -- used by the
icon builder and by CI -- has no fonts available and would draw a missing-glyph
box in place of a letter.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

BACKGROUND = QColor(32, 34, 40)
FOREGROUND = QColor(120, 200, 255)

# Fractions of the icon size: the glyph box, and the stroke drawn along it.
GLYPH_LEFT = 0.32
GLYPH_RIGHT = 0.68
GLYPH_TOP = 0.30
GLYPH_BOTTOM = 0.68
STROKE = 0.11


def _glyph_path(size: int) -> QPainterPath:
    """A lowercase u: left stem, bowl across the bottom, right stem back up."""
    left = size * GLYPH_LEFT
    right = size * GLYPH_RIGHT
    top = size * GLYPH_TOP
    bottom = size * GLYPH_BOTTOM
    radius = (right - left) / 2

    path = QPainterPath()
    path.moveTo(left, top)
    path.lineTo(left, bottom - radius)
    # Angles are measured with the y axis pointing down, so a positive sweep
    # from 180 degrees runs left -> bottom -> right. A negative one arcs over
    # the top and turns the glyph into an n.
    path.arcTo(QRectF(left, bottom - 2 * radius, 2 * radius, 2 * radius), 180, 180)
    path.lineTo(right, top)
    return path


def tray_pixmap(size: int = 64) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(BACKGROUND)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRect(2, 2, size - 4, size - 4), size * 0.22, size * 0.22)

    pen = QPen(FOREGROUND, max(1.0, size * STROKE))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(_glyph_path(size))
    painter.end()

    return pixmap


def tray_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        icon.addPixmap(tray_pixmap(size))
    return icon
