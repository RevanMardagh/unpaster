"""Regression coverage for the secret-snippet save defect in ManagerWindow.

`_save_current` used to re-derive the masked/editable decision from
`secret_check` and `_revealed` independently of what the body editor was
actually displaying. That let a masked body get written back as the literal
mask string, or a freshly typed body get discarded, depending on which
checkbox was toggled without pressing Reveal first. The fix makes
`body_edit.isReadOnly()` -- which `_render_body` sets deliberately -- the
single source of truth for what to save.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from unpaster import config, store
from unpaster.ui.manager import ManagerWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path):
    st, warnings = store.SnippetStore.load(tmp_path / "snippets.dat")
    assert warnings == []
    win = ManagerWindow(
        st, dict(config.DEFAULTS),
        on_config_changed=lambda cfg: None,
        on_quit=lambda: None,
    )
    return win


def _select(win, sid):
    """Refresh the list and select the row for sid. `_reload_list` itself
    calls `setCurrentRow`, which fires `currentItemChanged` ->
    `_load_selected()`, exactly like a user clicking the row -- needed here
    because the snippet was added directly through the store, bypassing the
    window's own Add button."""
    win._reload_list(select_id=sid)
    if win._current_id != sid:
        raise AssertionError(f"snippet {sid!r} not found in list")


def test_uncheck_secret_while_masked_preserves_body(window):
    snippet = window._store.add("db_password", "hunter2", secret=True)
    window._store.save()
    _select(window, snippet.id)

    # Masked and read-only; Reveal was never pressed.
    assert window.body_edit.isReadOnly()

    window.secret_check.setChecked(False)
    window._save_current()

    saved = window._store.get(snippet.id)
    assert saved.body == "hunter2"
    assert saved.secret is False


def test_check_secret_on_plain_snippet_keeps_the_typed_edit(window):
    snippet = window._store.add("admin_user", "old body", secret=False)
    window._store.save()
    _select(window, snippet.id)

    assert not window.body_edit.isReadOnly()
    window.body_edit.setPlainText("new body typed by user")
    window.secret_check.setChecked(True)
    window._save_current()

    saved = window._store.get(snippet.id)
    assert saved.body == "new body typed by user"
    assert saved.secret is True


def test_editing_after_reveal_still_saves_the_typed_text(window):
    snippet = window._store.add("api_key", "old secret", secret=True)
    window._store.save()
    _select(window, snippet.id)

    window.reveal_button.setChecked(True)
    assert not window.body_edit.isReadOnly()
    window.body_edit.setPlainText("updated secret")
    window._save_current()

    saved = window._store.get(snippet.id)
    assert saved.body == "updated secret"
    assert saved.secret is True
