import pytest

from unpaster import config, store
from unpaster.ui.manager import FOLLOW_SETTINGS, ManagerWindow


@pytest.fixture()
def window(tmp_path):
    snippet_store, _ = store.SnippetStore.load(tmp_path / "snippets.dat")
    win = ManagerWindow(snippet_store, dict(config.DEFAULTS),
                        on_config_changed=lambda cfg: None, on_quit=lambda: None)
    win.show()  # visibility of child widgets is only meaningful once shown
    yield win
    win.close()


def _select(window, snippet_id):
    window._reload_list(select_id=snippet_id)
    for row in range(window.snippet_list.count()):
        if window.snippet_list.item(row).data(256) == snippet_id:  # Qt.UserRole
            window.snippet_list.setCurrentRow(row)
            return
    raise AssertionError(f"snippet {snippet_id} not in the list")


def test_advanced_block_is_hidden_until_asked_for(window):
    snippet = window._store.add("plain", "x")
    _select(window, snippet.id)

    assert window.advanced_box.isVisible() is False
    window.advanced_button.setChecked(True)
    assert window.advanced_box.isVisible() is True


def test_send_keys_lives_in_the_advanced_block(window):
    assert window.keys_check.parent() is window.advanced_box


def test_method_and_newline_default_to_the_settings_value(window):
    snippet = window._store.add("plain", "x")
    _select(window, snippet.id)

    assert window.method_override() is None
    assert window.newline_override() is None


def test_saving_an_override_stores_it(window):
    snippet = window._store.add("cmd", "dir")
    _select(window, snippet.id)

    window.advanced_button.setChecked(True)
    window.snippet_method_combo.setCurrentIndex(window.snippet_method_combo.findData("scancode"))
    window.snippet_newline_combo.setCurrentIndex(window.snippet_newline_combo.findData("skip"))
    window.save_button.click()

    saved = window._store.get(snippet.id)
    assert saved.method == "scancode"
    assert saved.newline_mode == "skip"


def test_clearing_an_override_saves_it_back_to_default(window):
    snippet = window._store.add("cmd", "dir", method="scancode", newline_mode="skip")
    _select(window, snippet.id)

    window.snippet_method_combo.setCurrentIndex(window.snippet_method_combo.findData(FOLLOW_SETTINGS))
    window.snippet_newline_combo.setCurrentIndex(window.snippet_newline_combo.findData(FOLLOW_SETTINGS))
    window.save_button.click()

    saved = window._store.get(snippet.id)
    assert saved.method is None
    assert saved.newline_mode is None


def test_selecting_a_snippet_shows_its_overrides(window):
    plain = window._store.add("plain", "x")
    tuned = window._store.add("cmd", "dir", method="scancode", newline_mode="literal")

    _select(window, tuned.id)
    assert window.method_override() == "scancode"
    assert window.newline_override() == "literal"

    _select(window, plain.id)
    assert window.method_override() is None
    assert window.newline_override() is None


def test_a_snippet_with_advanced_values_opens_the_block(window):
    tuned = window._store.add("cmd", "dir", method="scancode")
    _select(window, tuned.id)
    assert window.advanced_box.isVisible() is True


def test_a_snippet_with_send_keys_opens_the_block(window):
    keys = window._store.add("login", "{enter}", send_keys=True)
    _select(window, keys.id)
    assert window.advanced_box.isVisible() is True


def test_a_plain_snippet_closes_the_block_again(window):
    tuned = window._store.add("cmd", "dir", method="scancode")
    plain = window._store.add("plain", "x")

    _select(window, tuned.id)
    _select(window, plain.id)
    assert window.advanced_box.isVisible() is False


def test_default_entries_name_the_current_setting(window):
    assert "unicode" in window.snippet_method_combo.itemText(window.snippet_method_combo.findData(FOLLOW_SETTINGS))
    assert "enter" in window.snippet_newline_combo.itemText(window.snippet_newline_combo.findData(FOLLOW_SETTINGS))
