"""Check that every recorded version agrees, and optionally that a tag matches.

pyproject.toml holds the version. version_info.txt repeats it four times for the
Windows version resource that PyInstaller stamps into the executable, so a bump
in one file and not the other ships a binary whose properties lie about which
build it is. The release workflow also passes the pushed tag through here, so a
mislabelled tag fails before anything is published.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
VERSION_INFO = ROOT / "version_info.txt"

_TUPLE_FIELDS = ("filevers", "prodvers")
_STRING_FIELDS = ("FileVersion", "ProductVersion")


def pyproject_version(text: str | None = None) -> str | None:
    if text is None:
        text = PYPROJECT.read_text(encoding="utf-8")
    return tomllib.loads(text).get("project", {}).get("version")


def _four_part(version: str) -> str:
    parts = version.split(".")
    parts += ["0"] * (4 - len(parts))
    return ".".join(parts[:4])


def _tuple_field(text: str, field: str) -> str | None:
    match = re.search(rf"{field}\s*=\s*\(([^)]*)\)", text)
    if match is None:
        return None
    return ".".join(part.strip() for part in match.group(1).split(","))


def _string_field(text: str, field: str) -> str | None:
    match = re.search(rf"StringStruct\(\s*'{field}'\s*,\s*'([^']*)'\s*\)", text)
    return match.group(1) if match else None


def problems(pyproject_text: str | None = None, version_info_text: str | None = None,
             tag: str | None = None) -> list[str]:
    """Return one message per disagreement. An empty list means all is well."""
    version = pyproject_version(pyproject_text)
    if version is None:
        return ["pyproject.toml has no project.version."]

    if version_info_text is None:
        version_info_text = VERSION_INFO.read_text(encoding="utf-8")

    expected = _four_part(version)
    found: list[str] = []

    for field in _TUPLE_FIELDS:
        actual = _tuple_field(version_info_text, field)
        if actual != expected:
            found.append(
                f"version_info.txt {field} is {actual}, expected {expected} "
                f"from pyproject.toml version {version}."
            )

    for field in _STRING_FIELDS:
        actual = _string_field(version_info_text, field)
        if actual != expected:
            found.append(
                f"version_info.txt {field} is {actual}, expected {expected} "
                f"from pyproject.toml version {version}."
            )

    if tag is not None and tag.lstrip("v") != version:
        found.append(f"Tag {tag} does not match the project version {version}.")

    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="release tag to compare, with or without a leading v")
    args = parser.parse_args(argv)

    found = problems(tag=args.tag)
    if found:
        for message in found:
            print(message)
        return 1

    print(f"Version {pyproject_version()} is recorded consistently.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
