import pytest

from unpaster import hotkey

CTRL_L = 0xA2
ALT_L = 0xA4
SHIFT_L = 0xA0
VK_V = 0x56
VK_A = 0x41
VK_ESC = 0x1B


@pytest.fixture()
def logic():
    return hotkey.HookLogic(hotkey.parse_hotkey("ctrl+alt+v"))


def press(logic, vk, injected=False):
    return logic.on_key(vk, True, injected)


def release(logic, vk, injected=False):
    return logic.on_key(vk, False, injected)


def test_plain_key_passes_through(logic):
    assert press(logic, VK_A) == "pass"


def test_modifier_press_passes_through(logic):
    assert press(logic, CTRL_L) == "pass"


def test_full_combo_reports_hotkey(logic):
    press(logic, CTRL_L)
    press(logic, ALT_L)
    assert press(logic, VK_V) == "hotkey"


def test_partial_combo_does_not_fire(logic):
    press(logic, CTRL_L)
    assert press(logic, VK_V) == "pass"


def test_extra_modifier_does_not_fire(logic):
    press(logic, CTRL_L)
    press(logic, ALT_L)
    press(logic, SHIFT_L)
    assert press(logic, VK_V) == "pass"


def test_releasing_a_modifier_disarms_the_combo(logic):
    press(logic, CTRL_L)
    press(logic, ALT_L)
    release(logic, ALT_L)
    assert press(logic, VK_V) == "pass"


def test_key_release_never_reports_hotkey(logic):
    press(logic, CTRL_L)
    press(logic, ALT_L)
    assert release(logic, VK_V) == "pass"


def test_injected_events_are_ignored(logic):
    press(logic, CTRL_L)
    press(logic, ALT_L)
    assert press(logic, VK_V, injected=True) == "pass"


def test_injected_modifier_does_not_change_state(logic):
    press(logic, CTRL_L, injected=True)
    press(logic, ALT_L)
    assert press(logic, VK_V) == "pass"


def test_escape_passes_through_when_not_armed(logic):
    assert press(logic, VK_ESC) == "pass"


def test_escape_is_claimed_while_armed(logic):
    logic.armed = True
    assert press(logic, VK_ESC) == "escape"


def test_escape_release_is_swallowed_while_armed(logic):
    logic.armed = True
    assert release(logic, VK_ESC) == "escape"


def test_escape_passes_again_after_disarm(logic):
    logic.armed = True
    press(logic, VK_ESC)
    logic.armed = False
    assert press(logic, VK_ESC) == "pass"


def test_hotkey_still_fires_while_armed(logic):
    logic.armed = True
    press(logic, CTRL_L)
    press(logic, ALT_L)
    assert press(logic, VK_V) == "hotkey"


def test_set_hotkey_rebinds(logic):
    logic.set_hotkey(hotkey.parse_hotkey("ctrl+shift+p"))
    press(logic, CTRL_L)
    press(logic, SHIFT_L)
    assert press(logic, 0x50) == "hotkey"


def test_set_hotkey_clears_stale_modifier_state(logic):
    press(logic, CTRL_L)
    press(logic, ALT_L)
    logic.set_hotkey(hotkey.parse_hotkey("ctrl+alt+v"))
    assert press(logic, VK_V) == "pass"


def test_repeat_press_of_combo_fires_each_time(logic):
    press(logic, CTRL_L)
    press(logic, ALT_L)
    assert press(logic, VK_V) == "hotkey"
    assert press(logic, VK_V) == "hotkey"
