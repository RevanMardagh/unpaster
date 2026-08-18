"""The Clipboard row: reads the host clipboard and types it like free text."""

import pytest
from PySide6.QtCore import Qt

from unpaster import store
from unpaster.ui.palette import CLIPBOARD_ID, PaletteWindow


@pytest.fixture()
def window(tmp_path):
    snippet_store, _ = store.SnippetStore.load(tmp_path / "snippets.dat")
    clipboard = {"text": "from the clipboard"}
    win = PaletteWindow(snippet_store, read_clipboard=lambda: clipboard["text"])
    win._clipboard = clipboard
    yield win
    win.close()


def select_clipboard_row(win):
    for row in range(win.list.count()):
        if win.list.item(row).data(Qt.UserRole) == CLIPBOARD_ID:
            win.list.setCurrentRow(row)
            return
    raise AssertionError("no clipboard row in the list")


def test_the_clipboard_row_is_offered_last(window):
    window._refresh("")
    assert window.list.item(window.list.count() - 1).data(Qt.UserRole) == CLIPBOARD_ID


def test_choosing_it_submits_the_clipboard_text(window):
    requests = []
    window.submitted.connect(requests.append)
    window._refresh("")
    select_clipboard_row(window)

    window._submit_selected()

    assert [r.text for r in requests] == ["from the clipboard"]


def test_the_clipboard_paste_follows_settings_and_stays_literal(window):
    requests = []
    window.submitted.connect(requests.append)
    window._refresh("")
    select_clipboard_row(window)

    window._submit_selected()

    request = requests[0]
    assert (request.send_keys, request.method, request.newline_mode) == (False, None, None)


def test_the_clipboard_is_read_when_chosen_not_when_opened(window):
    requests = []
    window.submitted.connect(requests.append)
    window._refresh("")
    select_clipboard_row(window)
    window._clipboard["text"] = "changed since the palette opened"

    window._submit_selected()

    assert requests[0].text == "changed since the palette opened"


def test_an_empty_clipboard_submits_nothing_and_keeps_the_palette_open(window):
    requests = []
    window.submitted.connect(requests.append)
    window._refresh("")
    select_clipboard_row(window)
    window._clipboard["text"] = ""

    window._submit_selected()

    assert requests == []
    assert window._closing is False
