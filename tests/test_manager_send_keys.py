import pytest

from unpaster import config, store
from unpaster.ui.manager import ManagerWindow


@pytest.fixture()
def window(tmp_path):
    snippet_store, _ = store.SnippetStore.load(tmp_path / "snippets.dat")
    win = ManagerWindow(snippet_store, dict(config.DEFAULTS),
                        on_config_changed=lambda cfg: None, on_quit=lambda: None)
    yield win
    win.close()


def _select(win, snippet_id):
    for row in range(win.snippet_list.count()):
        if win.snippet_list.item(row).data(256) == snippet_id:  # Qt.UserRole
            win.snippet_list.setCurrentRow(row)
            return
    raise AssertionError(f"snippet {snippet_id} not in the list")


def test_saving_with_the_box_checked_stores_the_flag(window):
    snippet = window._store.add("login", "")
    window._reload_list(select_id=snippet.id)
    _select(window, snippet.id)

    window.body_edit.setPlainText("admin{tab}pw{enter}")
    window.keys_check.setChecked(True)
    window._save_current()

    assert window._store.get(snippet.id).send_keys is True
    assert window._store.get(snippet.id).body == "admin{tab}pw{enter}"


def test_selecting_a_snippet_shows_its_flag(window):
    plain = window._store.add("plain", "x")
    keys = window._store.add("keys", "{enter}", send_keys=True)
    window._reload_list(select_id=keys.id)

    _select(window, keys.id)
    assert window.keys_check.isChecked() is True
    _select(window, plain.id)
    assert window.keys_check.isChecked() is False


def test_a_bad_token_blocks_the_save_and_names_the_token(window):
    snippet = window._store.add("login", "good")
    window._reload_list(select_id=snippet.id)
    _select(window, snippet.id)

    window.body_edit.setPlainText("{ctrl+banana}")
    window.keys_check.setChecked(True)
    window._save_current()

    assert window._store.get(snippet.id).body == "good"
    assert window._store.get(snippet.id).send_keys is False
    assert "{ctrl+banana}" in window.snippet_status.text()


def test_a_bad_token_is_ignored_while_the_box_is_unchecked(window):
    snippet = window._store.add("json", "")
    window._reload_list(select_id=snippet.id)
    _select(window, snippet.id)

    window.body_edit.setPlainText('{"port": 3389}')
    window.keys_check.setChecked(False)
    window._save_current()

    assert window._store.get(snippet.id).body == '{"port": 3389}'
    assert window.snippet_status.text() == ""
