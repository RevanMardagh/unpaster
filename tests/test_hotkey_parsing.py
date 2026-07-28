import pytest

from unpaster import hotkey


def test_parse_simple_combo():
    hk = hotkey.parse_hotkey("ctrl+alt+v")
    assert hk.mods == frozenset({"ctrl", "alt"})
    assert hk.vk == 0x56


def test_parse_is_case_and_space_insensitive():
    assert hotkey.parse_hotkey("  CTRL + Alt + V ") == hotkey.parse_hotkey("ctrl+alt+v")


def test_parse_accepts_aliases():
    assert hotkey.parse_hotkey("control+alt+v") == hotkey.parse_hotkey("ctrl+alt+v")
    assert hotkey.parse_hotkey("ctrl+menu+v") == hotkey.parse_hotkey("ctrl+alt+v")


def test_parse_digit_key():
    assert hotkey.parse_hotkey("ctrl+alt+1").vk == 0x31


def test_parse_function_key():
    assert hotkey.parse_hotkey("ctrl+f12").vk == 0x7B


def test_parse_named_key():
    assert hotkey.parse_hotkey("ctrl+alt+space").vk == 0x20
    assert hotkey.parse_hotkey("ctrl+alt+insert").vk == 0x2D


def test_parse_win_modifier():
    assert hotkey.parse_hotkey("win+v").mods == frozenset({"win"})


def test_parse_rejects_missing_modifier():
    with pytest.raises(hotkey.HotkeyParseError):
        hotkey.parse_hotkey("v")


def test_parse_rejects_modifier_only():
    with pytest.raises(hotkey.HotkeyParseError):
        hotkey.parse_hotkey("ctrl+alt")


def test_parse_rejects_unknown_key():
    with pytest.raises(hotkey.HotkeyParseError):
        hotkey.parse_hotkey("ctrl+alt+banana")


def test_parse_rejects_two_non_modifier_keys():
    with pytest.raises(hotkey.HotkeyParseError):
        hotkey.parse_hotkey("ctrl+a+b")


def test_parse_rejects_empty_string():
    with pytest.raises(hotkey.HotkeyParseError):
        hotkey.parse_hotkey("")


def test_format_uses_canonical_order():
    hk = hotkey.Hotkey(frozenset({"shift", "ctrl", "win", "alt"}), 0x56)
    assert hotkey.format_hotkey(hk) == "ctrl+alt+shift+win+v"


def test_format_round_trips_every_supported_key():
    for name in hotkey.VK_BY_NAME:
        text = f"ctrl+alt+{name}"
        assert hotkey.format_hotkey(hotkey.parse_hotkey(text)) == text


def test_tracker_starts_empty():
    assert hotkey.ModifierTracker().mods == frozenset()


def test_tracker_records_left_and_right_as_one_name():
    tracker = hotkey.ModifierTracker()
    tracker.press(0xA2)  # left ctrl
    assert tracker.mods == frozenset({"ctrl"})
    tracker.press(0xA3)  # right ctrl
    tracker.release(0xA2)
    assert tracker.mods == frozenset({"ctrl"})
    tracker.release(0xA3)
    assert tracker.mods == frozenset()


def test_tracker_ignores_non_modifier_keys():
    tracker = hotkey.ModifierTracker()
    tracker.press(0x41)
    assert tracker.mods == frozenset()


def test_tracker_handles_all_four_modifiers():
    tracker = hotkey.ModifierTracker()
    for vk in (0xA2, 0xA4, 0xA0, 0x5B):
        tracker.press(vk)
    assert tracker.mods == frozenset({"ctrl", "alt", "shift", "win"})


def test_tracker_reset_clears_everything():
    tracker = hotkey.ModifierTracker()
    tracker.press(0xA2)
    tracker.reset()
    assert tracker.mods == frozenset()


def test_tracker_release_without_press_is_harmless():
    tracker = hotkey.ModifierTracker()
    tracker.release(0xA2)
    assert tracker.mods == frozenset()


def test_vk_name_reverses_the_table():
    assert hotkey.vk_name(0x56) == "v"
    assert hotkey.vk_name(0x7B) == "f12"
    assert hotkey.vk_name(0x9999) is None
