"""palette_preview off must leave the palette exactly as it was before the
preview pane existed: no pane, the old height, and the clipboard read only at
submit time."""

import pytest
from PySide6.QtCore import Qt

from unpaster import store
from unpaster.ui.palette import CLIPBOARD_ID, PaletteWindow


def build(tmp_path, preview: bool | None, reads=None):
    snippet_store, _ = store.SnippetStore.load(tmp_path / "snippets.dat")
    snippet_store.add("admin_user", "svc-admin")

    def read_clipboard():
        if reads is not None:
            reads.append("read")
        return "from the clipboard"

    kwargs = {} if preview is None else {"get_config": lambda: {"palette_preview": preview}}
    return PaletteWindow(snippet_store, read_clipboard=read_clipboard,
                         take_foreground=lambda *_: None, **kwargs), snippet_store


@pytest.fixture()
def with_preview(tmp_path):
    win, _ = build(tmp_path / "on", True)
    yield win
    win.close()


@pytest.fixture()
def without_preview(tmp_path):
    win, _ = build(tmp_path / "off", False)
    yield win
    win.close()


def select_clipboard_row(win):
    for row in range(win.list.count()):
        if win.list.item(row).data(Qt.UserRole) == CLIPBOARD_ID:
            win.list.setCurrentRow(row)
            return
    raise AssertionError("no clipboard row in the list")


def test_the_preview_is_on_when_no_config_is_wired(tmp_path):
    win, _ = build(tmp_path, None)
    try:
        win.open_palette()
        assert not win.preview.isHidden()
    finally:
        win.close()


def test_the_pane_is_hidden_when_the_setting_is_off(without_preview):
    without_preview.open_palette()

    assert without_preview.preview.isHidden()


def test_the_pane_is_shown_when_the_setting_is_on(with_preview):
    with_preview.open_palette()

    assert not with_preview.preview.isHidden()


def test_the_palette_is_shorter_with_the_preview_off(with_preview, without_preview):
    with_preview.open_palette()
    without_preview.open_palette()

    assert without_preview.height() < with_preview.height()


def test_nothing_is_previewed_while_the_setting_is_off(without_preview):
    without_preview.open_palette()

    assert without_preview.preview.text() == ""


def test_the_clipboard_is_not_read_for_a_preview_while_the_setting_is_off(tmp_path):
    reads = []
    win, _ = build(tmp_path, False, reads=reads)
    try:
        win.open_palette()
        select_clipboard_row(win)
        assert reads == []
    finally:
        win.close()


def test_the_clipboard_is_still_read_at_submit_while_the_setting_is_off(tmp_path):
    reads = []
    win, _ = build(tmp_path, False, reads=reads)
    requests = []
    win.submitted.connect(requests.append)
    try:
        win.open_palette()
        select_clipboard_row(win)
        win._submit_selected()
    finally:
        win.close()

    assert reads == ["read"]
    assert requests[0].text == "from the clipboard"


def test_turning_the_setting_off_takes_effect_on_the_next_open(tmp_path):
    """The getter, not a copy: main rebinds its config dict on Apply, so a
    palette holding the old dict would keep the pane until a restart."""
    cfg = {"palette_preview": True}
    snippet_store, _ = store.SnippetStore.load(tmp_path / "snippets.dat")
    snippet_store.add("admin_user", "svc-admin")
    win = PaletteWindow(snippet_store, read_clipboard=lambda: "",
                        take_foreground=lambda *_: None, get_config=lambda: cfg)
    try:
        win.open_palette()
        assert not win.preview.isHidden()

        cfg["palette_preview"] = False
        win.open_palette()
        assert win.preview.isHidden()

        cfg["palette_preview"] = True
        win.open_palette()
        assert not win.preview.isHidden()
    finally:
        win.close()
