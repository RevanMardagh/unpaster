"""Hotkey parsing, modifier tracking, and the low-level keyboard hook.

A WH_KEYBOARD_LL hook is used rather than RegisterHotKey because a
full-screen RDP client with keyboard redirection swallows registered
hotkeys before they reach other processes. The low-level hook runs earlier
in the input pipeline and fires in both windowed and full-screen cases.
"""

from __future__ import annotations

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

    if not mods:
        raise HotkeyParseError("Hotkey needs at least one modifier such as Ctrl or Alt.")
    if len(keys) != 1:
        raise HotkeyParseError("Hotkey needs exactly one non-modifier key.")
    if keys[0] not in VK_BY_NAME:
        raise HotkeyParseError(f"Unknown key {keys[0]!r}.")

    return Hotkey(frozenset(mods), VK_BY_NAME[keys[0]])


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
