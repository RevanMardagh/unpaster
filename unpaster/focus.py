"""Capture the window that was focused before the palette appeared, and put
it back before typing. Every paste depends on this being correct."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.SetForegroundWindow.restype = wintypes.BOOL
_user32.BringWindowToTop.argtypes = [wintypes.HWND]
_user32.BringWindowToTop.restype = wintypes.BOOL
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
_user32.AttachThreadInput.restype = wintypes.BOOL
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class Win32FocusApi:
    def set_foreground(self, hwnd: int) -> bool:
        return bool(_user32.SetForegroundWindow(wintypes.HWND(hwnd)))

    def window_thread_id(self, hwnd: int) -> int:
        return int(_user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), None))

    def current_thread_id(self) -> int:
        return int(_kernel32.GetCurrentThreadId())

    def attach_thread_input(self, source: int, target: int, attach: bool) -> bool:
        return bool(_user32.AttachThreadInput(source, target, attach))

    def bring_to_top(self, hwnd: int) -> bool:
        return bool(_user32.BringWindowToTop(wintypes.HWND(hwnd)))


_DEFAULT_API = Win32FocusApi()


def get_foreground() -> int:
    handle = _user32.GetForegroundWindow()
    return int(handle) if handle else 0


def restore_foreground(hwnd: int, api: Win32FocusApi | None = None) -> bool:
    """Put hwnd back in the foreground, escalating only as far as needed."""
    if not hwnd:
        return False
    api = api or _DEFAULT_API

    if api.set_foreground(hwnd):
        return True

    target_thread = api.window_thread_id(hwnd)
    own_thread = api.current_thread_id()
    if target_thread and target_thread != own_thread:
        api.attach_thread_input(own_thread, target_thread, True)
        try:
            if api.set_foreground(hwnd):
                return True
        finally:
            api.attach_thread_input(own_thread, target_thread, False)

    return bool(api.bring_to_top(hwnd))
