# Manual smoke checklist

Automated tests cannot simulate a remote session. Run this list before each release.

## Setup

1. Add three snippets: a short one, a multi-line one, and one marked secret.
2. Confirm the secret snippet shows masked in the manager and shows only its name in the overlay.

## Local

- [ ] Hotkey opens the palette over Notepad; the snippet types correctly.
- [ ] Escape during the countdown types nothing.
- [ ] Escape mid-typing stops partway and the overlay says cancelled.
- [ ] Escape with no paste running reaches the focused app normally.
- [ ] Clicking through the overlay hits the window beneath it.
- [ ] The palette closes when it loses focus.

## RDP

- [ ] Windowed mstsc: hotkey fires, text arrives intact.
- [ ] Full-screen mstsc with keyboard redirection: hotkey still fires.
- [ ] Session keyboard layout differs from the host (set the session to a non-US layout):
      Unicode method types the correct characters.
- [ ] Elevated window inside the session: the overlay reports the elevation error
      rather than silently typing nothing.
- [ ] unpaster running elevated: typing into the elevated window succeeds.

## VNC

- [ ] RealVNC or TightVNC viewer: Unicode method types correctly.
- [ ] If it does not, the scancode fallback types correctly with matching layouts.

## Newline modes

- [ ] Enter: each line executes in a remote shell.
- [ ] Skip: the multi-line snippet arrives as one line.
- [ ] Literal: a line feed character is typed.

## Settings

- [ ] Rebinding the hotkey takes effect without a restart.
- [ ] An invalid rebind leaves the old hotkey working and reports inline.
- [ ] Character delay of 0 into a slow session; raise it until nothing drops.
- [ ] Test type reproduces the full countdown and progress sequence.
- [ ] Start with Windows survives a reboot.
- [ ] Close to tray on: the close button hides the window and the balloon appears once.
- [ ] Close to tray off: the close button quits and the hotkey stops.

## Recovery

- [ ] Corrupt `%APPDATA%\unpaster\snippets.dat` by hand: the app starts empty, keeps a
      `.bad-1` backup, and says so in a tray notification.
- [ ] Launch a second instance: it reports that unpaster is already running and exits.

## Packaged build

- [ ] `dist\unpaster.exe` starts with no traceback dialog and shows the tray icon.
- [ ] Settings and snippets written by the exe land in `%APPDATA%\unpaster\`, not beside the exe.
