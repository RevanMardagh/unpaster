"""Tray icon drawn in code so the project ships no binary assets."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

BACKGROUND = QColor(32, 34, 40)
FOREGROUND = QColor(120, 200, 255)


def tray_pixmap(size: int = 64) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(BACKGROUND)
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(QRect(2, 2, size - 4, size - 4), size * 0.22, size * 0.22)

    font = QFont("Segoe UI", int(size * 0.5))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(FOREGROUND)
    painter.drawText(QRect(0, 0, size, size), Qt.AlignCenter, "u")
    painter.end()

    return pixmap


def tray_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        icon.addPixmap(tray_pixmap(size))
    return icon
