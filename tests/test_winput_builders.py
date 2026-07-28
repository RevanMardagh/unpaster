import pytest

from unpaster import winput


def test_ascii_char_makes_one_down_up_pair():
    inputs = winput.unicode_inputs("a")
    assert len(inputs) == 2
    assert all(i.type == winput.INPUT_KEYBOARD for i in inputs)


def test_unicode_input_carries_char_in_wscan_not_wvk():
    down, up = winput.unicode_inputs("a")
    assert down.u.ki.wVk == 0
    assert down.u.ki.wScan == ord("a")
    assert up.u.ki.wScan == ord("a")


def test_unicode_input_sets_unicode_flag_and_keyup():
    down, up = winput.unicode_inputs("a")
    assert down.u.ki.dwFlags == winput.KEYEVENTF_UNICODE
    assert up.u.ki.dwFlags == winput.KEYEVENTF_UNICODE | winput.KEYEVENTF_KEYUP


def test_accented_char_uses_its_own_codepoint():
    down, _ = winput.unicode_inputs("ä")
    assert down.u.ki.wScan == 0x00E4


def test_astral_char_becomes_a_surrogate_pair():
    inputs = winput.unicode_inputs("\U0001F600")
    assert len(inputs) == 4
    assert [i.u.ki.wScan for i in inputs] == [0xD83D, 0xD83D, 0xDE00, 0xDE00]
    assert inputs[0].u.ki.dwFlags == winput.KEYEVENTF_UNICODE
    assert inputs[1].u.ki.dwFlags == winput.KEYEVENTF_UNICODE | winput.KEYEVENTF_KEYUP


def test_unicode_inputs_rejects_multi_char_input():
    with pytest.raises(ValueError):
        winput.unicode_inputs("ab")


def test_vk_inputs_sets_virtual_key_and_pair():
    down, up = winput.vk_inputs(winput.VK_RETURN)
    assert down.u.ki.wVk == winput.VK_RETURN
    assert down.u.ki.dwFlags == 0
    assert up.u.ki.dwFlags == winput.KEYEVENTF_KEYUP


def test_scancode_plain_char_makes_one_pair():
    inputs = winput.scancode_inputs("a", vk_scan=lambda ch: 0x41)
    assert len(inputs) == 2
    assert inputs[0].u.ki.wVk == 0x41
    assert inputs[1].u.ki.dwFlags == winput.KEYEVENTF_KEYUP


def test_scancode_shifted_char_wraps_in_shift():
    inputs = winput.scancode_inputs("A", vk_scan=lambda ch: 0x0141)
    assert len(inputs) == 4
    assert inputs[0].u.ki.wVk == winput.VK_SHIFT
    assert inputs[0].u.ki.dwFlags == 0
    assert inputs[1].u.ki.wVk == 0x41
    assert inputs[2].u.ki.wVk == 0x41
    assert inputs[2].u.ki.dwFlags == winput.KEYEVENTF_KEYUP
    assert inputs[3].u.ki.wVk == winput.VK_SHIFT
    assert inputs[3].u.ki.dwFlags == winput.KEYEVENTF_KEYUP


def test_scancode_altgr_char_wraps_in_ctrl_and_alt():
    inputs = winput.scancode_inputs("@", vk_scan=lambda ch: 0x0641)
    virtual_keys = [i.u.ki.wVk for i in inputs]
    assert virtual_keys == [
        winput.VK_CONTROL, winput.VK_MENU, 0x41, 0x41, winput.VK_MENU, winput.VK_CONTROL
    ]


def test_scancode_unmappable_char_raises():
    with pytest.raises(winput.UnmappableCharError):
        winput.scancode_inputs("中", vk_scan=lambda ch: -1)
