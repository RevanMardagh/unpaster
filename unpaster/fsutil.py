"""Filesystem helpers shared by the config and snippet stores."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

APP_NAME = "unpaster"


def app_dir() -> Path:
    """Return %APPDATA%\\unpaster, creating it if needed."""
    base = os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Roaming")
    target = Path(base) / APP_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write data to path so that a crash never leaves a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))
