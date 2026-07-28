# Changelog

Notable changes per release. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0 - 2026-07-28

First release.

### Added

- Global hotkey (`Ctrl+Alt+V` by default) opening a palette to pick a snippet or type a
  one-off string. The hotkey uses a `WH_KEYBOARD_LL` hook rather than `RegisterHotKey`, so
  it survives a full-screen RDP client with keyboard redirection.
- Typing through `SendInput`. The default Unicode method sends the character itself rather
  than a key position, so it is independent of the layout inside the remote session; a
  scancode method is available for viewers that ignore synthetic Unicode events.
- Snippet storage in `%APPDATA%\unpaster\snippets.dat`, encrypted with Windows DPAPI under
  the current user account. Snippets can be marked secret, which masks them in the manager
  and keeps them out of the overlay.
- Countdown and progress overlay, cancellable with Escape at any point.
- Newline handling per snippet or globally: press Enter, skip the newline, or type a
  literal line feed.
- Function keys F1 to F24 may be bound as hotkeys without a modifier.
- Key tokens in a snippet body, opt-in per snippet: `{ctrl+a}` for a combination,
  `{enter}` for a single key, `{wait:500}` for a pause, `{{` for a literal brace.
- Per-snippet overrides for the typing method and newline handling, under Advanced in the
  snippet editor. Unset options follow the Settings tab.
- Start with Windows, close-to-tray, and a single-instance guard.
- Configurable per-character delay for sessions that drop keystrokes.

### Notes

- The executable is unsigned. It installs a keyboard hook and calls `SendInput`, which is
  what a keylogger does too, so SmartScreen and some scanners will flag it.
- No clipboard API is used anywhere in the project. That is the point of the tool.
