"""Start-with-Windows support via the per-user Run key."""

from __future__ import annotations

import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "unpaster"


def current_command() -> str:
    """The command line that relaunches this app, quoted for the Run key."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m unpaster.main'


def is_enabled(*, key_path: str = RUN_KEY, value_name: str = VALUE_NAME) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.QueryValueEx(key, value_name)
    except FileNotFoundError:
        return False
    return True


def enable(exe_path: str | None = None, *, key_path: str = RUN_KEY,
           value_name: str = VALUE_NAME) -> None:
    command = f'"{exe_path}"' if exe_path else current_command()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command)


def disable(*, key_path: str = RUN_KEY, value_name: str = VALUE_NAME) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, value_name)
    except FileNotFoundError:
        pass
