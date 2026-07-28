"""SendInput plumbing.

The Unicode path sends the character itself rather than a key position, so
it is independent of the layout active inside the remote session. That is
what makes typing into RDP work. The scancode path is a fallback for viewers
that ignore synthetic Unicode events, and is only correct when the host and
session layouts agree.
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

INPUT_KEYBOARD = 1

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B

MAPVK_VK_TO_VSC = 0

_SHIFT_STATE_SHIFT = 1
_SHIFT_STATE_CONTROL = 2
_SHIFT_STATE_ALT = 4


class UnmappableCharError(Exception):
    """The character has no key combination on the current host layout."""


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _InputUnion(ctypes.Union):
    _fields_ = [("ki", _KeyboardInput), ("mi", _MouseInput), ("hi", _HardwareInput)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _InputUnion)]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
_user32.SendInput.restype = wintypes.UINT
_user32.VkKeyScanExW.argtypes = [wintypes.WCHAR, wintypes.HKL]
_user32.VkKeyScanExW.restype = ctypes.c_short
_user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
_user32.GetKeyboardLayout.restype = wintypes.HKL
_user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
_user32.MapVirtualKeyW.restype = wintypes.UINT


def _keyboard_input(*, vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    event = INPUT()
    event.type = INPUT_KEYBOARD
    event.u.ki = _KeyboardInput(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return event


def _utf16_units(ch: str) -> list[int]:
    if ord(ch) <= 0xFFFF:
        return [ord(ch)]
    encoded = ch.encode("utf-16-le")
    return [int.from_bytes(encoded[0:2], "little"), int.from_bytes(encoded[2:4], "little")]


def unicode_inputs(ch: str) -> list[INPUT]:
    """Build keydown/keyup pairs carrying the character as a Unicode value."""
    if len(ch) != 1:
        raise ValueError(f"expected a single character, got {ch!r}")
    events: list[INPUT] = []
    for unit in _utf16_units(ch):
        events.append(_keyboard_input(scan=unit, flags=KEYEVENTF_UNICODE))
        events.append(_keyboard_input(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    return events


def vk_inputs(vk: int) -> list[INPUT]:
    """Build a keydown/keyup pair for a virtual key such as Enter or Tab."""
    scan = _user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    return [
        _keyboard_input(vk=vk, scan=scan, flags=0),
        _keyboard_input(vk=vk, scan=scan, flags=KEYEVENTF_KEYUP),
    ]


def _real_vk_scan(ch: str) -> int:
    return _user32.VkKeyScanExW(ch, _user32.GetKeyboardLayout(0))


def scancode_inputs(ch: str, vk_scan: Callable[[str], int] | None = None) -> list[INPUT]:
    """Build a key sequence using the host layout. Fallback path only."""
    if len(ch) != 1:
        raise ValueError(f"expected a single character, got {ch!r}")
    scan_result = (vk_scan or _real_vk_scan)(ch)
    if scan_result == -1:
        raise UnmappableCharError(
            "a character in the text has no key on the current keyboard layout")

    vk = scan_result & 0xFF
    shift_state = (scan_result >> 8) & 0xFF

    modifiers: list[int] = []
    if shift_state & _SHIFT_STATE_SHIFT:
        modifiers.append(VK_SHIFT)
    if shift_state & _SHIFT_STATE_CONTROL:
        modifiers.append(VK_CONTROL)
    if shift_state & _SHIFT_STATE_ALT:
        modifiers.append(VK_MENU)

    events: list[INPUT] = []
    for modifier in modifiers:
        events.append(_keyboard_input(
            vk=modifier, scan=_user32.MapVirtualKeyW(modifier, MAPVK_VK_TO_VSC), flags=0))
    events.extend(vk_inputs(vk))
    for modifier in reversed(modifiers):
        events.append(_keyboard_input(
            vk=modifier, scan=_user32.MapVirtualKeyW(modifier, MAPVK_VK_TO_VSC),
            flags=KEYEVENTF_KEYUP))
    return events


def send_inputs(inputs: list[INPUT]) -> int:
    """Return how many events Windows accepted. A short count means blocked."""
    if not inputs:
        return 0
    array = (INPUT * len(inputs))(*inputs)
    return _user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))


NEWLINE_MODES = ("enter", "skip", "literal")


@dataclass
class TypeResult:
    status: str  # "done" | "cancelled" | "blocked" | "unmappable" | "badtoken"
    typed: int
    total: int
    detail: str = ""


class TokenError(Exception):
    """A {key} token in the text could not be understood."""


MOD_VK_BY_NAME = {"ctrl": VK_CONTROL, "alt": VK_MENU, "shift": VK_SHIFT, "win": VK_LWIN}
MOD_TOKEN_ORDER = ("ctrl", "alt", "shift", "win")

WAIT_PREFIX = "wait:"
WAIT_MAX_MS = 60_000


def chord_inputs(mods: tuple[int, ...], vk: int) -> list[INPUT]:
    """Hold the modifiers, tap the key, release the modifiers in reverse."""
    events: list[INPUT] = []
    for modifier in mods:
        events.append(_keyboard_input(
            vk=modifier, scan=_user32.MapVirtualKeyW(modifier, MAPVK_VK_TO_VSC), flags=0))
    events.extend(vk_inputs(vk))
    for modifier in reversed(mods):
        events.append(_keyboard_input(
            vk=modifier, scan=_user32.MapVirtualKeyW(modifier, MAPVK_VK_TO_VSC),
            flags=KEYEVENTF_KEYUP))
    return events


def _parse_wait(inner: str, token: str) -> tuple[str, object]:
    digits = inner[len(WAIT_PREFIX):].strip()
    if not digits.isdigit():
        raise TokenError(f"{token} needs a whole number of milliseconds.")
    milliseconds = int(digits)
    if milliseconds > WAIT_MAX_MS:
        raise TokenError(f"{token} is longer than the {WAIT_MAX_MS} ms limit.")
    return ("wait", milliseconds)


def _parse_token(inner: str) -> tuple[str, object]:
    """Turn the inside of a {...} token into one token tuple."""
    # Imported here so the module-level import graph stays winput -> nothing.
    from .hotkey import MOD_ALIASES, VK_BY_NAME

    token = "{" + inner + "}"
    spec = inner.strip().lower()
    if not spec:
        raise TokenError("An empty {} token is not a key.")
    if spec.startswith(WAIT_PREFIX):
        return _parse_wait(spec, token)

    mods: list[str] = []
    keys: list[str] = []
    for part in (p.strip() for p in spec.split("+")):
        if not part:
            raise TokenError(f"{token} has an empty part.")
        if part in MOD_ALIASES:
            mods.append(MOD_ALIASES[part])
        else:
            keys.append(part)

    if len(keys) != 1:
        raise TokenError(f"{token} needs exactly one non-modifier key.")
    if keys[0] not in VK_BY_NAME:
        raise TokenError(f"{token} names a key unpaster does not know.")

    vk = VK_BY_NAME[keys[0]]
    if not mods:
        return ("vk", vk)
    ordered = tuple(MOD_VK_BY_NAME[name] for name in MOD_TOKEN_ORDER if name in mods)
    return ("chord", (ordered, vk))


def expand_text(text: str, newline_mode: str,
                send_keys: bool = False) -> list[tuple[str, object]]:
    """Turn text into a flat token list of characters, keys, chords, and waits.

    With send_keys off every brace is a literal character, so a body holding
    JSON or shell braces types unchanged. With it on, {ctrl+a} presses a
    combination, {enter} taps a key, {wait:500} pauses, and {{ types one brace.
    """
    if newline_mode not in NEWLINE_MODES:
        raise ValueError(f"unknown newline_mode {newline_mode!r}")

    tokens: list[tuple[str, object]] = []
    index = 0
    while index < len(text):
        ch = text[index]

        if send_keys and ch == "{":
            if text.startswith("{{", index):
                tokens.append(("char", "{"))
                index += 2
                continue
            end = text.find("}", index + 1)
            if end == -1:
                raise TokenError("A { in the text is never closed by a }.")
            tokens.append(_parse_token(text[index + 1:end]))
            index = end + 1
            continue

        index += 1
        if ch == "\r":
            continue
        if ch == "\n":
            if newline_mode == "enter":
                tokens.append(("vk", VK_RETURN))
            elif newline_mode == "literal":
                tokens.append(("char", "\n"))
            continue
        if ch == "\t":
            tokens.append(("vk", VK_TAB))
            continue
        tokens.append(("char", ch))
    return tokens


def check_tokens(text: str) -> str | None:
    """Return the first token problem in text, or None when every token parses.

    Used by the editor so the user sees which token is wrong while they still
    have the body in front of them. At paste time the message is generic,
    because a snippet body may be a secret.
    """
    try:
        expand_text(text, "enter", send_keys=True)
    except TokenError as exc:
        return str(exc)
    return None


def type_text(
    text: str,
    *,
    method: str = "unicode",
    newline_mode: str = "enter",
    char_delay_ms: int = 12,
    send_keys: bool = False,
    cancel: threading.Event | None = None,
    progress=None,
    sender=send_inputs,
    sleep=time.sleep,
) -> TypeResult:
    """Type text one token at a time, reporting progress and honouring cancel."""
    if method not in ("unicode", "scancode"):
        raise ValueError(f"unknown method {method!r}")

    try:
        tokens = expand_text(text, newline_mode, send_keys=send_keys)
    except TokenError as exc:
        return TypeResult("badtoken", 0, 0, str(exc))

    total = len(tokens)
    typed = 0
    delay = char_delay_ms / 1000.0

    for kind, value in tokens:
        if cancel is not None and cancel.is_set():
            return TypeResult("cancelled", typed, total)

        if kind == "wait":
            # The pause replaces the per-character delay for this token, so a
            # {wait:500} is 500 ms and not 500 plus char_delay_ms.
            sleep(int(value) / 1000.0)
            typed += 1
            if progress is not None:
                progress(typed, total)
            continue

        try:
            if kind == "chord":
                mods, vk = value
                events = chord_inputs(mods, vk)
            elif kind == "vk":
                events = vk_inputs(int(value))
            elif method == "unicode":
                events = unicode_inputs(str(value))
            else:
                events = scancode_inputs(str(value))
        except UnmappableCharError as exc:
            return TypeResult("unmappable", typed, total, str(exc))

        accepted = sender(events)
        if accepted < len(events):
            return TypeResult(
                "blocked", typed, total,
                "Windows refused the input. The target window is probably elevated - "
                "run unpaster as administrator.",
            )

        typed += 1
        if progress is not None:
            progress(typed, total)
        if delay:
            sleep(delay)

    return TypeResult("done", typed, total)
