import os
from pathlib import Path

import pytest

from unpaster import fsutil


def test_app_dir_is_under_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert fsutil.app_dir() == tmp_path / "unpaster"


def test_app_dir_is_created(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    target = fsutil.app_dir()
    assert target.is_dir()


def test_atomic_write_bytes_creates_file(tmp_path):
    target = tmp_path / "data.bin"
    fsutil.atomic_write_bytes(target, b"hello")
    assert target.read_bytes() == b"hello"


def test_atomic_write_bytes_replaces_existing(tmp_path):
    target = tmp_path / "data.bin"
    target.write_bytes(b"old content that is longer")
    fsutil.atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"new"


def test_atomic_write_leaves_no_temp_files(tmp_path):
    target = tmp_path / "data.bin"
    fsutil.atomic_write_bytes(target, b"hello")
    assert [p.name for p in tmp_path.iterdir()] == ["data.bin"]


def test_failed_write_leaves_original_intact(tmp_path, monkeypatch):
    target = tmp_path / "data.bin"
    target.write_bytes(b"original")

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        fsutil.atomic_write_bytes(target, b"replacement")
    assert target.read_bytes() == b"original"
    assert [p.name for p in tmp_path.iterdir()] == ["data.bin"]


def test_atomic_write_text_round_trips_unicode(tmp_path):
    target = tmp_path / "data.txt"
    fsutil.atomic_write_text(target, "naïve — ok")
    assert target.read_text(encoding="utf-8") == "naïve — ok"
