# Changelog

One entry per release, under **New**, **Changed** and **Fixed**. Sections with nothing in
them are left out. Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### New

- A preview pane under the palette list, showing what the highlighted row would type. Long
  lines wrap and the pane clips rather than scrolls, so the palette keeps one height
  whatever is highlighted. A secret shows dots and its character count -- enough to tell
  two stored secrets apart, without putting the body on screen. The Clipboard row previews
  the current clipboard; submitting still re-reads it.
- A **Preview the highlighted snippet** setting, on by default. Turned off, the palette is
  what it was before the pane existed: no preview, the old height, and the clipboard read
  only when the Clipboard row is submitted.

## 0.1.1 - 2026-08-18

### New

- A **Clipboard** row at the end of the palette, which types whatever is on the local
  clipboard. It reads the clipboard as a source only; nothing is ever handed to the session
  through it. Like palette free text, the text is literal and follows Settings.

### Fixed

- The palette now takes the keyboard when the hotkey opens it. Windows refuses
  `SetForegroundWindow` to a process without input rights, which unpaster never has when the
  hotkey arrives through its keyboard hook, so the palette appeared but Enter and the arrow
  keys still went to the window behind it until it was clicked. It now borrows input rights
  from the window that had the foreground, the same escalation the paste path already used.

## 0.1.0 - 2026-07-29

First release.

### New

- Global hotkey, `Ctrl+Alt+V` by default, opening a palette to pick a snippet or type a
  one-off string. It uses a low-level keyboard hook instead of `RegisterHotKey`, so it still
  fires under a full-screen RDP client with keyboard redirection.
- Typing through `SendInput`. The default Unicode method sends the character itself rather
  than a key position, so it does not care which keyboard layout the remote session uses.
- A scancode method for viewers that ignore synthetic Unicode events, selectable globally or
  per snippet.
- Snippets stored in `%APPDATA%\unpaster\snippets.dat`, encrypted with Windows DPAPI under
  your user account.
- Secret snippets: masked in the manager and the palette, and never shown in the overlay.
- Countdown and progress overlay, cancellable with Escape at any point.
- Newline handling, globally or per snippet: press Enter, skip the newline, or type a literal
  line feed.
- Key tokens in a snippet body, off by default per snippet: `{ctrl+a}` for a combination,
  `{enter}` for a single key, `{wait:500}` for a pause, `{{` for a literal brace.
- Advanced block in the snippet editor holding the per-snippet typing method, newline
  handling and key-token toggle. Unset options follow the Settings tab, and the block opens
  by itself for a snippet that uses any of them.
- Function keys F1 to F24 can be bound as hotkeys with no modifier, for macro pads that send
  keys no physical keyboard has.
- Adjustable per-character delay for sessions that drop keystrokes.
- Start with Windows, close to tray, and a single-instance guard.
- Corrupt snippet files are kept as `snippets.dat.bad-N` and reported instead of being
  overwritten.
