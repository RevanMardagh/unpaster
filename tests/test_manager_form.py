from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from unpaster import config
from unpaster.ui import manager


def _press(widget, key, modifiers=Qt.NoModifier):
    widget.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, modifiers))


def test_capture_accepts_bare_function_key():
    edit = manager.HotkeyEdit("ctrl+alt+v")
    _press(edit, Qt.Key_F13)
    assert edit.text() == "f13"


def test_capture_accepts_function_key_with_modifier():
    edit = manager.HotkeyEdit("ctrl+alt+v")
    _press(edit, Qt.Key_F13, Qt.ControlModifier)
    assert edit.text() == "ctrl+f13"


def test_capture_ignores_bare_letter():
    edit = manager.HotkeyEdit("ctrl+alt+v")
    _press(edit, Qt.Key_A)
    assert edit.text() == "ctrl+alt+v"


def test_config_to_form_round_trips_defaults():
    form = manager.config_to_form(config.DEFAULTS)
    merged, warnings = manager.form_to_config(config.DEFAULTS, form)
    assert merged == config.DEFAULTS
    assert warnings == []


def test_form_to_config_applies_changes():
    form = manager.config_to_form(config.DEFAULTS)
    form["char_delay_ms"] = 30
    form["method"] = "scancode"
    merged, warnings = manager.form_to_config(config.DEFAULTS, form)
    assert merged["char_delay_ms"] == 30
    assert merged["method"] == "scancode"
    assert warnings == []


def test_form_to_config_rejects_bad_value_with_warning():
    form = manager.config_to_form(config.DEFAULTS)
    form["countdown_ms"] = 999_999
    merged, warnings = manager.form_to_config(config.DEFAULTS, form)
    assert merged["countdown_ms"] == config.DEFAULTS["countdown_ms"]
    assert len(warnings) == 1


def test_form_to_config_preserves_unknown_keys():
    base = dict(config.DEFAULTS, future_setting="keep me")
    form = manager.config_to_form(base)
    merged, _ = manager.form_to_config(base, form)
    assert merged["future_setting"] == "keep me"


def test_form_to_config_ignores_keys_not_in_the_form():
    form = {"char_delay_ms": 40}
    merged, warnings = manager.form_to_config(config.DEFAULTS, form)
    assert merged["char_delay_ms"] == 40
    assert merged["hotkey"] == config.DEFAULTS["hotkey"]
    assert warnings == []


def test_config_to_form_exposes_every_editable_setting():
    form = manager.config_to_form(config.DEFAULTS)
    assert set(form) == {
        "hotkey", "countdown_ms", "char_delay_ms", "method",
        "newline_mode", "overlay_enabled", "palette_preview", "close_to_tray",
        "autostart",
    }
