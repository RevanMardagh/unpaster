import pytest
from PySide6.QtWidgets import QMessageBox

from unpaster import config, store
from unpaster.ui.manager import ManagerWindow


@pytest.fixture()
def window(tmp_path):
    snippet_store, _ = store.SnippetStore.load(tmp_path / "snippets.dat")
    win = ManagerWindow(snippet_store, dict(config.DEFAULTS),
                        on_config_changed=lambda cfg: None, on_quit=lambda: None)
    yield win
    win.close()


def test_add_button_adds_a_snippet(window):
    window.add_button.click()
    assert len(window._store.snippets) == 1


def test_move_buttons_reorder_the_selection(window):
    window._store.add("a", "1")
    second = window._store.add("b", "2")
    window._reload_list(select_id=second.id)

    window.up_button.click()
    assert [s.name for s in window._store.snippets] == ["b", "a"]
    window.down_button.click()
    assert [s.name for s in window._store.snippets] == ["a", "b"]


def test_delete_button_removes_the_selection(window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    snippet = window._store.add("gone", "x")
    window._reload_list(select_id=snippet.id)

    window.delete_button.click()
    assert window._store.snippets == []


def test_save_button_writes_the_editor_contents(window):
    snippet = window._store.add("name", "old")
    window._reload_list(select_id=snippet.id)

    window.body_edit.setPlainText("new")
    window.save_button.click()
    assert window._store.get(snippet.id).body == "new"


def test_list_buttons_are_compact_and_labelled(window):
    for button in (window.add_button, window.delete_button,
                   window.up_button, window.down_button):
        assert button.text() != ""
        assert len(button.text()) == 1
        assert button.toolTip() != ""
        assert button.width() <= 40


def test_reveal_button_is_smaller_than_the_save_button(window):
    assert window.reveal_button.width() < window.save_button.sizeHint().width() * 2
    assert window.reveal_button.isCheckable()
