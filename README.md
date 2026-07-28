# unpaster

Types stored or entered text into RDP and VNC sessions where clipboard paste does not work.

Press the hotkey (Ctrl+Alt+V by default), pick a snippet or type a one-off string, and
unpaster restores focus to the session and types it character by character. The clipboard
is never used.

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
