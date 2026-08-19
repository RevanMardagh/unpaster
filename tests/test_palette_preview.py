"""The preview pane: shows what the highlighted row would type."""

import pytest
from PySide6.QtCore import Qt

from unpaster import store
from unpaster.ui import palette
from unpaster.ui.palette import CLIPBOARD_ID, PaletteWindow

NL = "\n"


def make_store(tmp_path):
    snippet_store, _ = store.SnippetStore.load(tmp_path / "snippets.dat")
    return snippet_store


@pytest.fixture()
def window(tmp_path):
    snippet_store = make_store(tmp_path)
    clipboard = {"text": "from the clipboard"}
    win = PaletteWindow(snippet_store, read_clipboard=lambda: clipboard["text"])
    win._clipboard = clipboard
    yield win, snippet_store, clipboard
    win.close()


def select_row_named(win, label_start):
    for row in range(win.list.count()):
        if win.list.item(row).text().startswith(label_start):
            win.list.setCurrentRow(row)
            return
    raise AssertionError(f"no row starting with {label_start!r}")


def select_clipboard_row(win):
    for row in range(win.list.count()):
        if win.list.item(row).data(Qt.UserRole) == CLIPBOARD_ID:
            win.list.setCurrentRow(row)
            return
    raise AssertionError("no clipboard row in the list")


# -- wrapping and clipping -----------------------------------------------


def test_a_short_body_previews_verbatim():
    assert palette.clip_preview("svc-admin") == "svc-admin"


def test_an_empty_body_says_so():
    assert palette.clip_preview("") == "(empty)"


def test_a_body_of_only_whitespace_still_previews_as_empty():
    assert palette.clip_preview("   \n  ") == "(empty)"


def test_a_long_line_wraps_across_the_rows():
    line = "x" * (palette.PREVIEW_COLS * 2)
    assert palette.clip_preview(line).splitlines() == [
        "x" * palette.PREVIEW_COLS,
        "x" * palette.PREVIEW_COLS,
    ]


def test_a_line_exactly_at_the_width_does_not_wrap():
    line = "x" * palette.PREVIEW_COLS
    assert palette.clip_preview(line) == line


def test_wrapping_keeps_every_character_in_order():
    line = "".join(str(n % 10) for n in range(palette.PREVIEW_COLS * 2 + 7))
    assert "".join(palette.clip_preview(line).splitlines()) == line


def test_a_line_too_long_for_the_whole_pane_is_marked_at_the_end():
    line = "x" * (palette.PREVIEW_COLS * palette.PREVIEW_LINES + 50)
    rows = palette.clip_preview(line).splitlines()
    assert len(rows) == palette.PREVIEW_LINES
    assert rows[-1] == "x" * (palette.PREVIEW_COLS - 1) + "…"


def test_extra_lines_are_dropped_and_marked_on_the_last_row_shown():
    """The mark cannot own a row: the pane is exactly PREVIEW_LINES rows tall,
    so a further row would be clipped and a cut preview would look complete."""
    body = NL.join(f"line{n}" for n in range(palette.PREVIEW_LINES + 3))
    rows = palette.clip_preview(body).splitlines()
    assert len(rows) == palette.PREVIEW_LINES
    assert rows[:-1] == [f"line{n}" for n in range(palette.PREVIEW_LINES - 1)]
    assert rows[-1] == f"line{palette.PREVIEW_LINES - 1}…"


def test_a_body_exactly_at_the_row_limit_is_not_marked():
    body = NL.join(f"line{n}" for n in range(palette.PREVIEW_LINES))
    assert palette.clip_preview(body) == body


def test_a_wrapped_line_uses_the_rows_a_later_line_wanted():
    body = "w" * (palette.PREVIEW_COLS + 3) + NL + "second" + NL + "third"
    rows = palette.clip_preview(body).splitlines()
    assert rows[:3] == ["w" * palette.PREVIEW_COLS, "www", "second"]


def test_no_row_is_ever_wider_than_the_pane():
    body = NL.join("q" * palette.PREVIEW_COLS * 3 for _ in range(4))
    rows = palette.clip_preview(body).splitlines()
    assert max(len(row) for row in rows) == palette.PREVIEW_COLS


def test_a_blank_line_inside_the_body_keeps_its_row():
    assert palette.clip_preview("a" + NL + NL + "b").splitlines() == ["a", "", "b"]


def test_carriage_returns_do_not_break_the_row_count():
    assert palette.clip_preview("a\r\nb").splitlines() == ["a", "b"]


# -- secrets -------------------------------------------------------------


def test_a_secret_is_masked_and_reports_its_length():
    assert palette.masked_preview("hunter2") == "•" * 7 + "  (7 chars)"


def test_a_long_secret_masks_at_the_cap_but_reports_the_real_length():
    assert palette.masked_preview("p" * 200) == "•" * palette.MASK_CAP + "  (200 chars)"


def test_a_one_character_secret_says_char_not_chars():
    assert palette.masked_preview("x") == "•  (1 char)"


def test_an_empty_secret_says_empty():
    assert palette.masked_preview("") == "(empty)"


def test_a_secret_snippet_previews_masked(tmp_path):
    snippet = make_store(tmp_path).add("db_password", "hunter2", secret=True)
    assert palette.preview_text(snippet) == palette.masked_preview("hunter2")


def test_a_secret_preview_never_contains_any_body_character(tmp_path):
    snippet = make_store(tmp_path).add("db_password", "Zq9!", secret=True)
    preview = palette.preview_text(snippet)
    assert not any(char in preview for char in "Zq9!")


def test_a_plain_snippet_previews_its_body(tmp_path):
    snippet = make_store(tmp_path).add("admin_user", "svc-admin")
    assert palette.preview_text(snippet) == "svc-admin"


# -- the widget ----------------------------------------------------------


def test_highlighting_a_snippet_shows_its_body(window):
    win, snippet_store, _ = window
    snippet_store.add("admin_user", "svc-admin")
    win._refresh("")

    select_row_named(win, "admin_user")

    assert win.preview.text() == "svc-admin"


def test_moving_the_highlight_updates_the_preview(window):
    win, snippet_store, _ = window
    snippet_store.add("admin_user", "svc-admin")
    snippet_store.add("port", "2222")
    win._refresh("")

    select_row_named(win, "admin_user")
    select_row_named(win, "port")

    assert win.preview.text() == "2222"


def test_an_arrow_key_from_the_search_box_updates_the_preview(window):
    win, snippet_store, _ = window
    snippet_store.add("admin_user", "svc-admin")
    snippet_store.add("port", "2222")
    win._refresh("")
    win.search.setFocus()
    assert win.focusWidget() is win.search

    win.keyPressEvent(_key_event(Qt.Key_Down))

    assert win.preview.text() == "2222"


def test_a_secret_snippet_is_masked_in_the_widget(window):
    win, snippet_store, _ = window
    snippet_store.add("db_password", "hunter2", secret=True)
    win._refresh("")

    select_row_named(win, "db_password")

    assert "hunter2" not in win.preview.text()
    assert win.preview.text() == palette.masked_preview("hunter2")


def test_the_clipboard_row_previews_the_clipboard(window):
    win, _, _ = window
    win._refresh("")

    select_clipboard_row(win)

    assert win.preview.text() == "from the clipboard"


def test_an_empty_clipboard_says_so(window):
    win, _, clipboard = window
    clipboard["text"] = ""
    win._refresh("")

    select_clipboard_row(win)

    assert win.preview.text() == "(clipboard is empty)"


def test_the_clipboard_preview_wraps_like_a_body(window):
    win, _, clipboard = window
    clipboard["text"] = "y" * (palette.PREVIEW_COLS + 10)
    win._refresh("")

    select_clipboard_row(win)

    assert win.preview.text().splitlines() == ["y" * palette.PREVIEW_COLS, "y" * 10]


def test_the_preview_is_empty_when_no_row_matches(window):
    win, snippet_store, _ = window
    snippet_store.add("admin_user", "svc-admin")
    win._refresh("")
    select_row_named(win, "admin_user")

    win.list.clear()  # what a refresh with no rows at all would leave behind
    win._update_preview()

    assert win.preview.text() == ""


def test_reopening_the_palette_previews_the_first_row(window):
    win, snippet_store, _ = window
    snippet_store.add("admin_user", "svc-admin")

    win._refresh("")

    assert win.preview.text() == "svc-admin"


def test_the_palette_height_does_not_change_with_the_preview(window):
    win, snippet_store, _ = window
    snippet_store.add("short", "a")
    snippet_store.add("tall", NL.join("line" for _ in range(40)))
    win._refresh("")

    select_row_named(win, "short")
    win.adjustSize()
    short_height = win.height()
    select_row_named(win, "tall")
    win.adjustSize()

    assert win.height() == short_height


def _key_event(key):
    from PySide6.QtGui import QKeyEvent

    return QKeyEvent(QKeyEvent.KeyPress, key, Qt.NoModifier)
