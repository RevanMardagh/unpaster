import json

from unpaster import config


def test_defaults_match_spec():
    assert config.DEFAULTS == {
        "schema_version": 1,
        "hotkey": "ctrl+alt+v",
        "countdown_ms": 3000,
        "char_delay_ms": 12,
        "method": "unicode",
        "newline_mode": "enter",
        "overlay_enabled": True,
        "close_to_tray": True,
        "autostart": False,
    }


def test_validate_empty_returns_defaults():
    cfg, warnings = config.validate({})
    assert cfg == config.DEFAULTS
    assert warnings == []


def test_validate_keeps_valid_values():
    cfg, warnings = config.validate({"char_delay_ms": 40, "method": "scancode"})
    assert cfg["char_delay_ms"] == 40
    assert cfg["method"] == "scancode"
    assert warnings == []


def test_validate_rejects_out_of_range_number():
    cfg, warnings = config.validate({"char_delay_ms": 5000})
    assert cfg["char_delay_ms"] == 12
    assert len(warnings) == 1
    assert "char_delay_ms" in warnings[0]


def test_validate_rejects_wrong_type():
    cfg, warnings = config.validate({"overlay_enabled": "yes"})
    assert cfg["overlay_enabled"] is True
    assert len(warnings) == 1


def test_validate_rejects_unknown_choice():
    cfg, warnings = config.validate({"newline_mode": "carriage"})
    assert cfg["newline_mode"] == "enter"
    assert len(warnings) == 1


def test_validate_accepts_countdown_zero():
    cfg, warnings = config.validate({"countdown_ms": 0})
    assert cfg["countdown_ms"] == 0
    assert warnings == []


def test_validate_preserves_unknown_keys():
    cfg, warnings = config.validate({"future_setting": [1, 2]})
    assert cfg["future_setting"] == [1, 2]
    assert warnings == []


def test_load_missing_file_returns_defaults(tmp_path):
    cfg, warnings = config.load(tmp_path / "absent.json")
    assert cfg == config.DEFAULTS
    assert warnings == []


def test_load_corrupt_file_returns_defaults_with_warning(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    cfg, warnings = config.load(path)
    assert cfg == config.DEFAULTS
    assert len(warnings) == 1
    assert "config" in warnings[0].lower()


def test_load_non_object_returns_defaults_with_warning(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    cfg, warnings = config.load(path)
    assert cfg == config.DEFAULTS
    assert len(warnings) == 1


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "config.json"
    cfg = dict(config.DEFAULTS, char_delay_ms=25, hotkey="ctrl+shift+p")
    config.save(path, cfg)
    loaded, warnings = config.load(path)
    assert loaded == cfg
    assert warnings == []


def test_save_writes_readable_json(tmp_path):
    path = tmp_path / "config.json"
    config.save(path, config.DEFAULTS)
    assert json.loads(path.read_text(encoding="utf-8"))["hotkey"] == "ctrl+alt+v"
