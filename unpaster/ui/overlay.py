"""Translucent countdown and progress overlay.

The overlay must never take keyboard focus. If it did, it would undo the
foreground restore that the whole paste depends on. It is also transparent
to the mouse so clicks pass through to the session beneath.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

WIDTH = 260
HEIGHT = 96
INSET = 24
FADE_MS = 800
ERROR_MS = 4000

BACKGROUND = QColor(20, 22, 28, 225)
TEXT = QColor(235, 238, 245)
MUTED = QColor(150, 158, 175)
ACCENT = QColor(120, 200, 255)
ERROR = QColor(255, 110, 110)
TRACK = QColor(60, 65, 78)

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.GetWindowLongW.restype = wintypes.LONG
_user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
_user32.SetWindowLongW.restype = wintypes.LONG
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL


def overlay_position(screen: tuple[int, int, int, int], size: tuple[int, int],
                     inset: int) -> tuple[int, int]:
    """Top-right corner of the given screen rect, inset from both edges."""
    screen_x, screen_y, screen_w, _screen_h = screen
    width, _height = size
    x = screen_x + screen_w - width - inset
    return max(screen_x, x), screen_y + inset


class OverlayWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.resize(WIDTH, HEIGHT)

        self._title = ""
        self._headline = ""
        self._typed = 0
        self._total = 0
        self._show_bar = False
        self._colour = ACCENT

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_now)

    # -- placement ---------------------------------------------------------

    def move_to_screen_of(self, hwnd: int) -> None:
        screen = self._screen_for(hwnd)
        rect = screen.geometry()
        x, y = overlay_position((rect.x(), rect.y(), rect.width(), rect.height()),
                                (self.width(), self.height()), INSET)
        self.move(x, y)

    def _screen_for(self, hwnd: int):
        if hwnd:
            for candidate in QGuiApplication.screens():
                geometry = candidate.geometry()
                point = _window_center(hwnd)
                if point is not None and geometry.contains(point[0], point[1]):
                    return candidate
        return QGuiApplication.primaryScreen()

    # -- states ------------------------------------------------------------

    def _present(self, title: str, headline: str, colour: QColor, show_bar: bool,
                 auto_hide_ms: int | None) -> None:
        self._title = title
        self._headline = headline
        self._colour = colour
        self._show_bar = show_bar
        self._hide_timer.stop()
        if auto_hide_ms:
            self._hide_timer.start(auto_hide_ms)
        if not self.isVisible():
            self.show()
            self._apply_no_activate()
        self.raise_()
        self.update()

    def show_countdown(self, name: str, seconds: int) -> None:
        self._present(name, str(seconds), ACCENT, False, None)

    def show_progress(self, name: str, typed: int, total: int) -> None:
        self._typed = typed
        self._total = total
        self._present(name, f"{typed} / {total}", ACCENT, True, None)

    def show_done(self) -> None:
        self._present(self._title, "done", ACCENT, False, FADE_MS)

    def show_cancelled(self) -> None:
        self._present(self._title, "cancelled", MUTED, False, FADE_MS)

    def show_error(self, message: str) -> None:
        self._present(self._title, message, ERROR, False, ERROR_MS)

    def hide_now(self) -> None:
        self._hide_timer.stop()
        self.hide()

    def _apply_no_activate(self) -> None:
        hwnd = int(self.winId())
        style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setBrush(BACKGROUND)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)

        title_font = QFont("Segoe UI", 9)
        painter.setFont(title_font)
        painter.setPen(MUTED)
        painter.drawText(QRect(16, 12, WIDTH - 32, 18),
                         Qt.AlignLeft | Qt.AlignVCenter, self._title)

        headline_font = QFont("Segoe UI", 16)
        headline_font.setBold(True)
        painter.setFont(headline_font)
        painter.setPen(self._colour)
        painter.drawText(QRect(16, 32, WIDTH - 32, 30),
                         Qt.AlignLeft | Qt.AlignVCenter, self._headline)

        if self._show_bar and self._total:
            track = QRect(16, HEIGHT - 26, WIDTH - 32, 6)
            painter.setPen(Qt.NoPen)
            painter.setBrush(TRACK)
            painter.drawRoundedRect(track, 3, 3)
            filled = QRect(track)
            filled.setWidth(int(track.width() * self._typed / self._total))
            painter.setBrush(self._colour)
            painter.drawRoundedRect(filled, 3, 3)

        painter.end()


def _window_center(hwnd: int) -> tuple[int, int] | None:
    rect = wintypes.RECT()
    if not _user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return None
    return (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
