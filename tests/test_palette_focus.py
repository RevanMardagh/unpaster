"""Opening the palette has to claim the keyboard, not only become visible.

The hotkey fires from a low-level keyboard hook while another application owns
the foreground. Windows refuses SetForegroundWindow to a process that has no
input rights, so Qt's activateWindow() alone leaves the palette visible but
unfocused -- Enter and the arrow keys go to the window behind it until the user
clicks. open_palette() therefore escalates through focus.take_foreground().
"""

import pytest

from unpaster import store
from unpaster.ui.palette import PaletteWindow


@pytest.fixture()
def calls():
    return []


@pytest.fixture()
def window(tmp_path, calls):
    snippet_store, _ = store.SnippetStore.load(tmp_path / "snippets.dat")
    win = PaletteWindow(
        snippet_store,
        take_foreground=lambda hwnd, donor: calls.append((hwnd, donor)) or True,
    )
    yield win
    win.close()


def test_opening_claims_the_foreground_for_the_palette(window, calls):
    window.open_palette(donor_hwnd=4321)

    assert calls == [(int(window.winId()), 4321)]


def test_the_donor_is_optional(window, calls):
    window.open_palette()

    assert calls == [(int(window.winId()), 0)]


def test_the_search_box_holds_the_keyboard_focus(window):
    """focusWidget, not hasFocus: hasFocus also requires an active window, and
    the offscreen platform CI runs on never activates one."""
    window.open_palette(donor_hwnd=4321)

    assert window.focusWidget() is window.search
