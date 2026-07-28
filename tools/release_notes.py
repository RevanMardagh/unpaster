"""Assemble a release note from the download preamble and CHANGELOG.md.

The release workflow writes the result to a file and hands it to the release
action, so the New/Changed/Fixed entries written at development time become the
release note instead of being retyped. GitHub still appends its own generated
list of commits underneath.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"

PREAMBLE = """Download `unpaster.exe` below. No installer or runtime required.

**Verify it** against `unpaster.exe.sha256`:

```powershell
Get-FileHash unpaster.exe -Algorithm SHA256 | Select-Object -ExpandProperty Hash
```

**Windows will warn you.** The executable is unsigned and installs a low-level keyboard
hook, so SmartScreen and some scanners flag it. Why that is unavoidable, and what to check
instead: https://github.com/RevanMardagh/unpaster#windows-will-warn-you

Settings and snippets are written to `%APPDATA%\\unpaster\\`, never beside the executable.
"""


class MissingVersion(Exception):
    """CHANGELOG.md has no section for that version."""


def section(version: str, text: str | None = None) -> str:
    """Return the changelog body for one version, without its heading."""
    if text is None:
        text = CHANGELOG.read_text(encoding="utf-8")
    wanted = version.lstrip("v")

    # A version heading runs until the next one, or to the end of the file.
    pattern = rf"^##\s+{re.escape(wanted)}\b.*?$(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise MissingVersion(f"CHANGELOG.md has no section for {wanted}.")
    return match.group(1).strip()


def compose(version: str, text: str | None = None) -> str:
    return f"{PREAMBLE}\n{section(version, text)}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="with or without a leading v")
    parser.add_argument("--output", required=True, help="file to write the note to")
    args = parser.parse_args(argv)

    try:
        note = compose(args.version)
    except MissingVersion as exc:
        print(exc)
        return 1

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(note, encoding="utf-8")
    print(f"Wrote {len(note)} characters of release note to {target}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
