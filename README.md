# unpaster

Types stored or entered text into RDP and VNC sessions where clipboard paste does not work.

Press the hotkey (Ctrl+Alt+V by default), pick a snippet or type a one-off string, and
unpaster restores focus to the session and types it character by character. The clipboard
is never used.

## Per-snippet options

The Settings tab holds the defaults. Any snippet can override them under **Advanced** in
the snippet editor: the typing method (`unicode` or `scancode`), newline handling (`enter`,
`skip` or `literal`), and whether key tokens are parsed. Each option shows
`Default (<setting>)` until you choose otherwise, so a snippet follows Settings unless it
says otherwise — useful when one target is a VNC viewer that needs the scancode fallback
while everything else stays on Unicode.

The block opens by itself for a snippet that already uses any of it, so a non-default
choice is never hidden. Palette free text always follows Settings.

## Key tokens

A snippet can send key combinations instead of only characters. Tick **Send key tokens**
under Advanced on the snippet, then write tokens in the body:

| Token | Effect |
|---|---|
| `{ctrl+a}` | Holds Ctrl, taps A, releases Ctrl. Any of `ctrl`, `alt`, `shift`, `win` combine. |
| `{enter}` `{tab}` `{esc}` `{f5}` `{up}` `{delete}` | Taps the key on its own. |
| `{wait:500}` | Pauses 500 ms, for remote apps that drop keys after a dialog opens. Maximum 60000. |
| `{{` | Types one literal `{`. |

The toggle is per snippet and off by default, so a body holding JSON or shell braces types
unchanged and needs no escaping. Palette free text is always literal. An unusable token is
reported when the snippet is saved; the paste-time message stays generic because a body may
be a secret.

## Why not just paste

Clipboard redirection is often disabled by policy, blocked by the session host, or
ignored by the remote application. unpaster sidesteps all of it by sending keystrokes.

## Install from source

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m unpaster.main
```

Pinned versions are also available as `requirements.txt` (runtime) and
`requirements-dev.txt` (tests and packaging).

## Run the tests

```powershell
.venv\Scripts\python.exe -m pytest
```

## Build the executable

```powershell
.venv\Scripts\python.exe -m tools.make_icon
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm unpaster.spec
```

The frozen entry point is `run_unpaster.py`, not `unpaster/main.py`: PyInstaller runs the
entry module as `__main__` with no package context, so the package's relative imports
would fail if `main.py` were used directly.

## Antivirus

unpaster installs a low-level keyboard hook and calls `SendInput`. That combination is
also what a keylogger does, so some scanners flag the executable. There is no way to
implement the feature without it.

## Storage and secrets

Snippets live in `%APPDATA%\unpaster\snippets.dat`, encrypted with Windows DPAPI under
your user account. This protects the file against copying, backup exfiltration, and other
users on the machine. It does not protect against malware already running as you — such
code can call the same API. Snippets marked secret are masked in the interface and never
shown in the overlay.

## License

Copyright (C) 2026 RevanMardagh

This program is free software: you can redistribute it and/or modify it under the terms of
the GNU General Public License as published by the Free Software Foundation, either version
3 of the License, or (at your option) any later version. It is distributed in the hope that
it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See [LICENSE](LICENSE) for details.

Version 3 rather than 2 is deliberate: PySide6 and Qt are LGPL-3.0, and LGPL-3.0 code
cannot be combined with a GPL-2.0-only work. Building the executable bundles Qt, so a
binary you distribute carries Qt's LGPL-3.0 obligations alongside this project's GPL.
