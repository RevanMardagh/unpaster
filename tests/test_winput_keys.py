import pytest

from unpaster import winput


class FakeSender:
    def __init__(self):
        self.batches = []

    def __call__(self, inputs):
        self.batches.append(inputs)
        return len(inputs)


def no_sleep(_seconds):
    pass


# -- tokenizing ------------------------------------------------------------


def test_braces_stay_literal_when_send_keys_is_off():
    assert winput.expand_text("{ctrl+a}", "enter") == [("char", c) for c in "{ctrl+a}"]


def test_chord_token_carries_modifier_and_key():
    assert winput.expand_text("{ctrl+a}", "enter", send_keys=True) == [
        ("chord", ((winput.VK_CONTROL,), 0x41))
    ]


def test_chord_modifiers_use_canonical_order():
    assert winput.expand_text("{shift+ctrl+end}", "enter", send_keys=True) == [
        ("chord", ((winput.VK_CONTROL, winput.VK_SHIFT), 0x23))
    ]


def test_win_modifier_token():
    assert winput.expand_text("{win+r}", "enter", send_keys=True) == [
        ("chord", ((winput.VK_LWIN,), 0x52))
    ]


def test_token_without_modifier_becomes_a_plain_virtual_key():
    assert winput.expand_text("{enter}", "enter", send_keys=True) == [
        ("vk", winput.VK_RETURN)
    ]


def test_function_key_token():
    assert winput.expand_text("{f5}", "enter", send_keys=True) == [("vk", 0x74)]


def test_wait_token_carries_milliseconds():
    assert winput.expand_text("{wait:500}", "enter", send_keys=True) == [("wait", 500)]


def test_tokens_mix_with_typed_text():
    assert winput.expand_text("ab{tab}c", "enter", send_keys=True) == [
        ("char", "a"), ("char", "b"), ("vk", winput.VK_TAB), ("char", "c"),
    ]


def test_tokens_are_case_and_space_insensitive():
    assert (winput.expand_text("{ CTRL + A }", "enter", send_keys=True)
            == winput.expand_text("{ctrl+a}", "enter", send_keys=True))


def test_token_aliases_match_the_hotkey_names():
    assert (winput.expand_text("{control+a}", "enter", send_keys=True)
            == winput.expand_text("{ctrl+a}", "enter", send_keys=True))


def test_double_brace_is_one_literal_brace():
    assert winput.expand_text("{{ctrl}", "enter", send_keys=True) == [
        ("char", c) for c in "{ctrl}"
    ]


def test_closing_brace_alone_is_literal():
    assert winput.expand_text("a}b", "enter", send_keys=True) == [
        ("char", "a"), ("char", "}"), ("char", "b"),
    ]


def test_newlines_still_expand_inside_a_keys_snippet():
    assert winput.expand_text("a\n{tab}", "enter", send_keys=True) == [
        ("char", "a"), ("vk", winput.VK_RETURN), ("vk", winput.VK_TAB),
    ]


def test_unclosed_brace_raises():
    with pytest.raises(winput.TokenError):
        winput.expand_text("a{ctrl+a", "enter", send_keys=True)


def test_empty_token_raises():
    with pytest.raises(winput.TokenError):
        winput.expand_text("{}", "enter", send_keys=True)


def test_unknown_key_token_raises():
    with pytest.raises(winput.TokenError):
        winput.expand_text("{ctrl+banana}", "enter", send_keys=True)


def test_modifier_only_token_raises():
    with pytest.raises(winput.TokenError):
        winput.expand_text("{ctrl}", "enter", send_keys=True)


def test_two_non_modifier_keys_in_one_token_raise():
    with pytest.raises(winput.TokenError):
        winput.expand_text("{ctrl+a+b}", "enter", send_keys=True)


@pytest.mark.parametrize("body", ["{wait:}", "{wait:abc}", "{wait:-5}", "{wait:999999}"])
def test_bad_wait_value_raises(body):
    with pytest.raises(winput.TokenError):
        winput.expand_text(body, "enter", send_keys=True)


def test_token_error_names_the_offending_token():
    with pytest.raises(winput.TokenError) as excinfo:
        winput.expand_text("{ctrl+banana}", "enter", send_keys=True)
    assert "{ctrl+banana}" in str(excinfo.value)


def test_check_tokens_returns_the_first_problem():
    assert winput.check_tokens("a{tab}b") is None
    assert "{ctrl+banana}" in winput.check_tokens("a{ctrl+banana}")


# -- chord input building --------------------------------------------------


def test_chord_inputs_wraps_the_key_in_its_modifiers():
    inputs = winput.chord_inputs((winput.VK_CONTROL,), 0x41)
    assert [i.u.ki.wVk for i in inputs] == [
        winput.VK_CONTROL, 0x41, 0x41, winput.VK_CONTROL
    ]
    assert inputs[0].u.ki.dwFlags == 0
    assert inputs[-1].u.ki.dwFlags == winput.KEYEVENTF_KEYUP


def test_chord_inputs_releases_modifiers_in_reverse_order():
    inputs = winput.chord_inputs((winput.VK_CONTROL, winput.VK_SHIFT), 0x23)
    assert [i.u.ki.wVk for i in inputs] == [
        winput.VK_CONTROL, winput.VK_SHIFT, 0x23, 0x23,
        winput.VK_SHIFT, winput.VK_CONTROL,
    ]


# -- typing ----------------------------------------------------------------


def test_type_text_sends_a_chord_as_one_batch():
    sender = FakeSender()
    result = winput.type_text("{ctrl+a}", send_keys=True, sender=sender, sleep=no_sleep)
    assert result.status == "done"
    assert len(sender.batches) == 1
    assert len(sender.batches[0]) == 4


def test_type_text_types_braces_literally_when_send_keys_is_off():
    sender = FakeSender()
    result = winput.type_text("{a}", sender=sender, sleep=no_sleep)
    assert result.status == "done"
    assert result.total == 3


def test_wait_token_sleeps_its_own_duration():
    slept = []
    result = winput.type_text("{wait:500}", send_keys=True, char_delay_ms=12,
                              sender=FakeSender(), sleep=slept.append)
    assert result.status == "done"
    assert slept == [0.5]


def test_wait_token_sends_no_input():
    sender = FakeSender()
    winput.type_text("{wait:10}", send_keys=True, sender=sender, sleep=no_sleep)
    assert sender.batches == []


def test_bad_token_reports_status_without_typing():
    sender = FakeSender()
    result = winput.type_text("{ctrl+banana}", send_keys=True, sender=sender, sleep=no_sleep)
    assert result.status == "badtoken"
    assert result.typed == 0
    assert sender.batches == []
    assert "{ctrl+banana}" in result.detail


def test_cancel_stops_before_a_wait():
    import threading

    cancel = threading.Event()
    cancel.set()
    slept = []
    result = winput.type_text("{wait:500}", send_keys=True, cancel=cancel,
                              sender=FakeSender(), sleep=slept.append)
    assert result.status == "cancelled"
    assert slept == []
