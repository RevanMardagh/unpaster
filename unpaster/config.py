"""Application settings: load, validate, save.

Validation never raises. An invalid field falls back to its default and
produces a warning string; the application always starts.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import fsutil

DEFAULTS: dict = {
    "schema_version": 1,
    "hotkey": "ctrl+alt+v",
    "countdown_ms": 3000,
    "char_delay_ms": 12,
    "method": "unicode",
    "newline_mode": "enter",
    "overlay_enabled": True,
    "close_to_tray": True,
    "autostart": False,
}

METHODS = ("unicode", "scancode")
NEWLINE_MODES = ("enter", "skip", "literal")

COUNTDOWN_MAX_MS = 30_000
CHAR_DELAY_MAX_MS = 200


def config_path() -> Path:
    return fsutil.app_dir() / "config.json"


def _check_int(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _validate_field(key: str, value: object) -> bool:
    if key == "schema_version":
        return _check_int(value, 1, 1)
    if key == "hotkey":
        return isinstance(value, str) and bool(value.strip())
    if key == "countdown_ms":
        return _check_int(value, 0, COUNTDOWN_MAX_MS)
    if key == "char_delay_ms":
        return _check_int(value, 0, CHAR_DELAY_MAX_MS)
    if key == "method":
        return value in METHODS
    if key == "newline_mode":
        return value in NEWLINE_MODES
    if key in ("overlay_enabled", "close_to_tray", "autostart"):
        return isinstance(value, bool)
    return True


def validate(raw: dict) -> tuple[dict, list[str]]:
    """Return a complete config plus warnings for every field replaced."""
    warnings: list[str] = []
    result = dict(DEFAULTS)

    for key, value in raw.items():
        if key not in DEFAULTS:
            result[key] = value
            continue
        if _validate_field(key, value):
            result[key] = value
        else:
            warnings.append(f"Setting {key} had invalid value {value!r}; using default {DEFAULTS[key]!r}.")

    return result, warnings


def load(path: Path) -> tuple[dict, list[str]]:
    if not path.exists():
        return dict(DEFAULTS), []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULTS), ["Could not read config file; using defaults."]
    if not isinstance(raw, dict):
        return dict(DEFAULTS), ["Config file was not an object; using defaults."]
    return validate(raw)


def save(path: Path, cfg: dict) -> None:
    fsutil.atomic_write_text(path, json.dumps(cfg, indent=2, sort_keys=True) + "\n")
