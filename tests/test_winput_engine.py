import threading

import pytest

from unpaster import winput


class FakeSender:
    """Records every batch handed to SendInput and reports full acceptance."""

    def __init__(self, accept_all=True):
        self.batches = []
        self.accept_all = accept_all

    def __call__(self, inputs):
        self.batches.append(inputs)
        return len(inputs) if self.accept_all else 0


def no_sleep(_seconds):
    pass


def test_expand_plain_text():
    assert winput.expand_text("hi", "enter") == [("char", "h"), ("char", "i")]


def test_expand_newline_as_enter():
    assert winput.expand_text("a\nb", "enter") == [
        ("char", "a"), ("vk", winput.VK_RETURN), ("char", "b")
    ]


def test_expand_newline_skipped():
    assert winput.expand_text("a\nb", "skip") == [("char", "a"), ("char", "b")]


def test_expand_newline_literal():
    assert winput.expand_text("a\nb", "literal") == [
        ("char", "a"), ("char", "\n"), ("char", "b")
    ]


def test_expand_strips_carriage_returns():
    assert winput.expand_text("a\r\nb", "enter") == [
        ("char", "a"), ("vk", winput.VK_RETURN), ("char", "b")
    ]


def test_expand_tab_becomes_virtual_key():
    assert winput.expand_text("a\tb", "enter") == [
        ("char", "a"), ("vk", winput.VK_TAB), ("char", "b")
    ]


def test_expand_rejects_unknown_newline_mode():
    with pytest.raises(ValueError):
        winput.expand_text("a", "wrong")


def test_type_text_sends_one_batch_per_token():
    sender = FakeSender()
    result = winput.type_text("abc", sender=sender, sleep=no_sleep)
    assert result.status == "done"
    assert result.typed == 3
    assert result.total == 3
    assert len(sender.batches) == 3


def test_type_text_uses_unicode_path_by_default():
    sender = FakeSender()
    winput.type_text("a", sender=sender, sleep=no_sleep)
    assert sender.batches[0][0].u.ki.wScan == ord("a")
    assert sender.batches[0][0].u.ki.dwFlags == winput.KEYEVENTF_UNICODE


def test_type_text_scancode_path_uses_virtual_keys():
    sender = FakeSender()
    winput.type_text("a", method="scancode", sender=sender, sleep=no_sleep)
    assert sender.batches[0][0].u.ki.wVk != 0


def test_type_text_reports_progress_per_token():
    seen = []
    winput.type_text("abc", sender=FakeSender(), sleep=no_sleep,
                     progress=lambda typed, total: seen.append((typed, total)))
    assert seen == [(1, 3), (2, 3), (3, 3)]


def test_type_text_sleeps_between_characters():
    slept = []
    winput.type_text("abc", char_delay_ms=20, sender=FakeSender(), sleep=slept.append)
    assert slept == [0.02, 0.02, 0.02]


def test_zero_delay_never_sleeps():
    slept = []
    winput.type_text("abc", char_delay_ms=0, sender=FakeSender(), sleep=slept.append)
    assert slept == []


def test_short_send_count_reports_blocked():
    sender = FakeSender(accept_all=False)
    result = winput.type_text("abc", sender=sender, sleep=no_sleep)
    assert result.status == "blocked"
    assert result.typed == 0
    assert len(sender.batches) == 1
    assert "administrator" in result.detail


def test_cancel_stops_before_the_next_token():
    cancel = threading.Event()
    sender = FakeSender()

    def cancel_after_first(typed, total):
        if typed == 1:
            cancel.set()

    result = winput.type_text("abcdef", sender=sender, sleep=no_sleep,
                              cancel=cancel, progress=cancel_after_first)
    assert result.status == "cancelled"
    assert result.typed == 1
    assert len(sender.batches) == 1


def test_cancel_set_before_start_types_nothing():
    cancel = threading.Event()
    cancel.set()
    sender = FakeSender()
    result = winput.type_text("abc", sender=sender, sleep=no_sleep, cancel=cancel)
    assert result.status == "cancelled"
    assert sender.batches == []


def test_empty_text_completes_immediately():
    result = winput.type_text("", sender=FakeSender(), sleep=no_sleep)
    assert result.status == "done"
    assert result.total == 0


def test_unmappable_char_on_scancode_path_reports_status(monkeypatch):
    def boom(ch, vk_scan=None):
        raise winput.UnmappableCharError("nope")

    monkeypatch.setattr(winput, "scancode_inputs", boom)
    result = winput.type_text("a", method="scancode", sender=FakeSender(), sleep=no_sleep)
    assert result.status == "unmappable"


def test_type_text_rejects_unknown_method():
    with pytest.raises(ValueError):
        winput.type_text("a", method="telepathy", sender=FakeSender(), sleep=no_sleep)
