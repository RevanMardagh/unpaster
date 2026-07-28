"""Hotkey parsing, modifier tracking, and the low-level keyboard hook.

A WH_KEYBOARD_LL hook is used rather than RegisterHotKey because a
full-screen RDP client with keyboard redirection swallows registered
hotkeys before they reach other processes. The low-level hook runs earlier
in the input pipeline and fires in both windowed and full-screen cases.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from dataclasses import dataclass

MOD_ORDER = ("ctrl", "alt", "shift", "win")

MOD_ALIASES = {
    "ctrl": "ctrl", "control": "ctrl",
    "alt": "alt", "menu": "alt",
    "shift": "shift",
    "win": "win", "super": "win", "meta": "win",
}

# Left/right variants and the generic virtual key all collapse to one name.
MOD_VKS = {
    0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
    0x12: "alt", 0xA4: "alt", 0xA5: "alt",
    0x10: "shift", 0xA0: "shift", 0xA1: "shift",
    0x5B: "win", 0x5C: "win",
}


def _build_vk_table() -> dict[str, int]:
    table: dict[str, int] = {}
    for index, letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
        table[letter] = 0x41 + index
    for digit in range(10):
        table[str(digit)] = 0x30 + digit
    for number in range(1, 25):
        table[f"f{number}"] = 0x6F + number
    table.update({
        "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "esc": 0x1B,
        "space": 0x20, "pageup": 0x21, "pagedown": 0x22, "end": 0x23,
        "home": 0x24, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
        "insert": 0x2D, "delete": 0x2E,
    })
    return table


VK_BY_NAME: dict[str, int] = _build_vk_table()
_NAME_BY_VK: dict[int, str] = {vk: name for name, vk in VK_BY_NAME.items()}

# F1-F24 may be bound on their own. Every other key needs a modifier, because
# the hook swallows whatever it matches and a bare letter would make that
# letter untypable everywhere until the binding is changed.
FUNCTION_KEY_VKS: frozenset[int] = frozenset(VK_BY_NAME[f"f{n}"] for n in range(1, 25))


class HotkeyParseError(Exception):
    """The hotkey text could not be turned into a usable binding."""


@dataclass(frozen=True)
class Hotkey:
    mods: frozenset[str]
    vk: int

    def matches(self, vk: int, mods: frozenset[str]) -> bool:
        """Exact match, so ctrl+alt+v does not fire while Shift is held."""
        return vk == self.vk and mods == self.mods


def vk_name(vk: int) -> str | None:
    return _NAME_BY_VK.get(vk)


def parse_hotkey(text: str) -> Hotkey:
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if not parts:
        raise HotkeyParseError("Hotkey is empty.")

    mods: set[str] = set()
    keys: list[str] = []
    for part in parts:
        if part in MOD_ALIASES:
            mods.add(MOD_ALIASES[part])
        else:
            keys.append(part)

    if len(keys) != 1:
        raise HotkeyParseError("Hotkey needs exactly one non-modifier key.")
    if keys[0] not in VK_BY_NAME:
        raise HotkeyParseError(f"Unknown key {keys[0]!r}.")

    vk = VK_BY_NAME[keys[0]]
    if not mods and vk not in FUNCTION_KEY_VKS:
        raise HotkeyParseError(
            f"{keys[0]} needs at least one modifier such as Ctrl or Alt. "
            "Only F1-F24 can be used on their own."
        )

    return Hotkey(frozenset(mods), vk)


def format_hotkey(hk: Hotkey) -> str:
    parts = [mod for mod in MOD_ORDER if mod in hk.mods]
    parts.append(vk_name(hk.vk) or f"vk{hk.vk:02x}")
    return "+".join(parts)


class ModifierTracker:
    """Tracks which modifier keys are physically down."""

    def __init__(self) -> None:
        self._down: set[int] = set()

    def press(self, vk: int) -> None:
        if vk in MOD_VKS:
            self._down.add(vk)

    def release(self, vk: int) -> None:
        self._down.discard(vk)

    def reset(self) -> None:
        self._down.clear()

    @property
    def mods(self) -> frozenset[str]:
        return frozenset(MOD_VKS[vk] for vk in self._down)


VK_ESCAPE = 0x1B

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
WM_TIMER = 0x0113
LLKHF_INJECTED = 0x10
HC_ACTION = 0

REINSTALL_INTERVAL_MS = 60_000
_REINSTALL_TIMER_ID = 1


class HookInstallError(Exception):
    """SetWindowsHookExW failed."""


class HookLogic:
    """Decides what to do with each key event. No Windows calls, no Qt."""

    def __init__(self, hk: Hotkey) -> None:
        self._hotkey = hk
        self._tracker = ModifierTracker()
        self.armed = False

    def set_hotkey(self, hk: Hotkey) -> None:
        self._hotkey = hk
        self._tracker.reset()

    def on_key(self, vk: int, is_down: bool, injected: bool) -> str:
        """Return "hotkey", "escape", or "pass"."""
        if injected:
            # Our own SendInput output must never feed back into the hook.
            return "pass"

        if vk in MOD_VKS:
            if is_down:
                self._tracker.press(vk)
            else:
                self._tracker.release(vk)
            return "pass"

        if vk == VK_ESCAPE and self.armed:
            return "escape"

        if is_down and self._hotkey.matches(vk, self._tracker.mods):
            return "hotkey"

        return "pass"


class _KbdLlHookStruct(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


_LRESULT = ctypes.c_ssize_t
_HOOKPROC = ctypes.WINFUNCTYPE(_LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
_user32.SetWindowsHookExW.restype = wintypes.HHOOK
_user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
_user32.UnhookWindowsHookEx.restype = wintypes.BOOL
_user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
_user32.CallNextHookEx.restype = _LRESULT
_user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.GetMessageW.restype = wintypes.BOOL
_user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.PostThreadMessageW.restype = wintypes.BOOL
_user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p]
_user32.SetTimer.restype = ctypes.c_void_p
_user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_void_p]
_user32.KillTimer.restype = wintypes.BOOL
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class KeyboardHook:
    """Runs a WH_KEYBOARD_LL hook on a dedicated thread with a message loop.

    The hook is reinstalled every 60 seconds. Windows offers no way to ask
    whether a hook is still alive -- an idle hook and a hook the OS dropped
    for being slow look identical -- so liveness is guaranteed by reinstalling
    rather than inferred from a probe. The reinstall runs on the hook thread,
    so there is no race with the callback.
    """

    def __init__(self, hk: Hotkey, on_hotkey, on_escape) -> None:
        self.logic = HookLogic(hk)
        self._on_hotkey = on_hotkey
        self._on_escape = on_escape
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._handle = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        # A reference must outlive the hook or the trampoline is collected.
        self._callback = _HOOKPROC(self._dispatch)

    def start(self) -> None:
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="unpaster-hook", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)
        if self._error is not None:
            raise self._error

    def stop(self) -> None:
        if self._thread_id:
            _user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        self._thread_id = 0

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_hotkey(self, hk: Hotkey) -> None:
        self.logic.set_hotkey(hk)

    def set_armed(self, armed: bool) -> None:
        self.logic.armed = armed

    def _install(self) -> None:
        handle = _user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._callback, None, 0)
        if not handle:
            raise HookInstallError(
                f"SetWindowsHookExW failed with error {ctypes.get_last_error()}"
            )
        self._handle = handle

    def _uninstall(self) -> None:
        if self._handle:
            _user32.UnhookWindowsHookEx(self._handle)
            self._handle = None

    def _run(self) -> None:
        self._thread_id = int(_kernel32.GetCurrentThreadId())
        try:
            self._install()
        except BaseException as exc:
            self._error = exc
            self._ready.set()
            return

        _user32.SetTimer(None, _REINSTALL_TIMER_ID, REINSTALL_INTERVAL_MS, None)
        self._ready.set()

        message = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_TIMER:
                self._uninstall()
                try:
                    self._install()
                except HookInstallError:
                    pass  # Next tick tries again; the app stays usable from the tray.

        _user32.KillTimer(None, _REINSTALL_TIMER_ID)
        self._uninstall()

    def _dispatch(self, code, wparam, lparam):
        """Hook callback. Must return in well under a millisecond."""
        if code != HC_ACTION:
            return _user32.CallNextHookEx(None, code, wparam, lparam)

        info = ctypes.cast(lparam, ctypes.POINTER(_KbdLlHookStruct)).contents
        is_down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
        injected = bool(info.flags & LLKHF_INJECTED)

        action = self.logic.on_key(int(info.vkCode), is_down, injected)

        if action == "hotkey":
            self._on_hotkey()
            return 1
        if action == "escape":
            self._on_escape()
            return 1
        return _user32.CallNextHookEx(None, code, wparam, lparam)
