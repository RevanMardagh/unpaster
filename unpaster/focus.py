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


def _activate(hwnd: int, donor_hwnd: int, api: Win32FocusApi | None) -> bool:
    """Activate hwnd, borrowing input rights from donor_hwnd's thread if needed.

    SetForegroundWindow is refused unless the caller already has input rights,
    which a background process does not. AttachThreadInput joins our thread to
    the queue of a thread that does have them, and Windows then accepts the
    call. Attaching can itself fail -- an elevated foreground window will not
    share its queue with an unelevated process -- so the last resort only
    raises the window, which is visible but not focused.
    """
    if not hwnd:
        return False
    api = api or _DEFAULT_API

    if api.set_foreground(hwnd):
        return True

    donor_thread = api.window_thread_id(donor_hwnd) if donor_hwnd else 0
    own_thread = api.current_thread_id()
    if donor_thread and donor_thread != own_thread:
        api.attach_thread_input(own_thread, donor_thread, True)
        try:
            if api.set_foreground(hwnd):
                return True
        finally:
            api.attach_thread_input(own_thread, donor_thread, False)

    return bool(api.bring_to_top(hwnd))


def restore_foreground(hwnd: int, api: Win32FocusApi | None = None) -> bool:
    """Put hwnd back in the foreground, escalating only as far as needed.

    The window being restored is the one holding the rights we lack, so it is
    its own donor.
    """
    return _activate(hwnd, hwnd, api)


def take_foreground(hwnd: int, donor_hwnd: int = 0, api: Win32FocusApi | None = None) -> bool:
    """Bring one of our own windows to the front with the keyboard focus.

    donor_hwnd is the window that owns the foreground -- usually the one just
    captured by get_foreground(). Our own window cannot be the donor: its
    thread is this thread, so there would be no rights to borrow.
    """
    return _activate(hwnd, donor_hwnd, api)
