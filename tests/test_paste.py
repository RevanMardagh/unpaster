import threading

import pytest

from unpaster import config, paste, winput


class FakeOverlay:
    def __init__(self):
        self.calls = []

    def show_countdown(self, name, seconds):
        self.calls.append(("countdown", name, seconds))

    def show_progress(self, name, typed, total):
        self.calls.append(("progress", name, typed, total))

    def show_done(self):
        self.calls.append(("done",))

    def show_cancelled(self):
        self.calls.append(("cancelled",))

    def show_error(self, message):
        self.calls.append(("error", message))

    def hide_now(self):
        self.calls.append(("hide",))


class FakeScheduler:
    def __init__(self):
        self.queue = []

    def __call__(self, delay_ms, fn):
        self.queue.append((delay_ms, fn))

    def run_all(self):
        while self.queue:
            _delay, fn = self.queue.pop(0)
            fn()


def immediate(fn):
    fn()


def make_controller(*, cfg=None, restore=True, type_result=None, typed_log=None):
    overlay = FakeOverlay()
    scheduler = FakeScheduler()
    armed = []
    finished = []
    settings = dict(config.DEFAULTS)
    settings.update(cfg or {})

    def fake_type_text(text, **kwargs):
        if typed_log is not None:
            typed_log.append((text, kwargs))
        progress = kwargs.get("progress")
        cancel = kwargs.get("cancel")
        if cancel is not None and cancel.is_set():
            return winput.TypeResult("cancelled", 0, len(text))
        if progress is not None:
            progress(len(text), len(text))
        return type_result or winput.TypeResult("done", len(text), len(text))

    controller = paste.PasteController(
        overlay=overlay,
        set_armed=armed.append,
        get_config=lambda: settings,
        schedule=scheduler,
        run_async=immediate,
        post_to_ui=immediate,
        restore_foreground=lambda hwnd: restore,
        type_text=fake_type_text,
        on_finished=finished.append,
    )
    return controller, overlay, scheduler, armed, finished


def test_focus_failure_aborts_before_typing():
    typed = []
    controller, overlay, scheduler, armed, finished = make_controller(
        restore=False, typed_log=typed)
    controller.start("admin_user", "secret", 4321)
    scheduler.run_all()

    assert typed == []
    assert finished[0].status == "focus-failed"
    assert overlay.calls[-1][0] == "error"
    assert armed[-1] is False
    assert controller.busy is False


def test_countdown_counts_down_then_types():
    typed = []
    controller, overlay, scheduler, _armed, finished = make_controller(
        cfg={"countdown_ms": 3000}, typed_log=typed)
    controller.start("admin_user", "abc", 4321)
    scheduler.run_all()

    countdowns = [call for call in overlay.calls if call[0] == "countdown"]
    assert [call[2] for call in countdowns] == [3, 2, 1]
    assert typed and typed[0][0] == "abc"
    assert finished[0].status == "done"


def test_zero_countdown_still_waits_for_the_settle_delay():
    controller, _overlay, scheduler, _armed, finished = make_controller(
        cfg={"countdown_ms": 0})
    controller.start("admin_user", "abc", 4321)
    assert scheduler.queue[0][0] == paste.SETTLE_MS
    scheduler.run_all()
    assert finished[0].status == "done"


def test_progress_is_forwarded_to_the_overlay():
    controller, overlay, scheduler, _armed, _finished = make_controller(
        cfg={"countdown_ms": 0})
    controller.start("admin_user", "abc", 4321)
    scheduler.run_all()
    assert ("progress", "admin_user", 3, 3) in overlay.calls


def test_overlay_never_receives_the_text():
    controller, overlay, scheduler, _armed, _finished = make_controller(
        cfg={"countdown_ms": 1000})
    controller.start("db_password", "hunter2", 4321)
    scheduler.run_all()
    assert not any("hunter2" in str(call) for call in overlay.calls)


def test_cancel_during_countdown_types_nothing():
    typed = []
    controller, overlay, scheduler, armed, finished = make_controller(
        cfg={"countdown_ms": 3000}, typed_log=typed)
    controller.start("admin_user", "abc", 4321)
    controller.cancel()
    scheduler.run_all()

    assert typed == []
    assert finished[0].status == "cancelled"
    assert ("cancelled",) in overlay.calls
    assert armed[-1] is False


def test_cancel_during_typing_is_passed_to_the_engine():
    controller, overlay, scheduler, _armed, finished = make_controller(
        cfg={"countdown_ms": 0})

    original_start = controller._begin_typing

    def cancel_then_type():
        controller.cancel()
        original_start()

    controller._begin_typing = cancel_then_type
    controller.start("admin_user", "abc", 4321)
    scheduler.run_all()

    assert finished[0].status == "cancelled"


def test_blocked_result_shows_an_error():
    blocked = winput.TypeResult("blocked", 0, 3, "run unpaster as administrator")
    controller, overlay, scheduler, _armed, finished = make_controller(
        cfg={"countdown_ms": 0}, type_result=blocked)
    controller.start("admin_user", "abc", 4321)
    scheduler.run_all()

    assert finished[0].status == "blocked"
    assert overlay.calls[-1] == ("error", "run unpaster as administrator")


def test_unmappable_result_does_not_leak_a_character_to_the_overlay():
    leaky_detail = "'中' has no key on the current layout"
    unmappable = winput.TypeResult("unmappable", 0, 3, leaky_detail)
    controller, overlay, scheduler, _armed, finished = make_controller(
        cfg={"countdown_ms": 0}, type_result=unmappable)
    controller.start("admin_user", "中bc", 4321)
    scheduler.run_all()

    assert finished[0].status == "unmappable"
    assert not any("中" in str(call) for call in overlay.calls)


def test_typing_settings_come_from_the_config():
    typed = []
    controller, _overlay, scheduler, _armed, _finished = make_controller(
        cfg={"countdown_ms": 0, "char_delay_ms": 40, "method": "scancode",
             "newline_mode": "skip"},
        typed_log=typed)
    controller.start("admin_user", "abc", 4321)
    scheduler.run_all()

    _text, kwargs = typed[0]
    assert kwargs["char_delay_ms"] == 40
    assert kwargs["method"] == "scancode"
    assert kwargs["newline_mode"] == "skip"
    assert isinstance(kwargs["cancel"], threading.Event)


def test_overlay_disabled_suppresses_every_overlay_call():
    typed = []
    controller, overlay, scheduler, _armed, finished = make_controller(
        cfg={"countdown_ms": 2000, "overlay_enabled": False}, typed_log=typed)
    controller.start("admin_user", "abc", 4321)
    scheduler.run_all()

    assert overlay.calls == []
    assert typed and finished[0].status == "done"


def test_a_second_start_while_busy_is_ignored():
    typed = []
    controller, _overlay, scheduler, _armed, finished = make_controller(
        cfg={"countdown_ms": 3000}, typed_log=typed)
    controller.start("first", "aaa", 4321)
    controller.start("second", "bbb", 4321)
    scheduler.run_all()

    assert [entry[0] for entry in typed] == ["aaa"]
    assert len(finished) == 1


def test_controller_is_reusable_after_finishing():
    typed = []
    controller, _overlay, scheduler, _armed, finished = make_controller(
        cfg={"countdown_ms": 0}, typed_log=typed)
    controller.start("first", "aaa", 4321)
    scheduler.run_all()
    controller.start("second", "bbb", 4321)
    scheduler.run_all()

    assert [entry[0] for entry in typed] == ["aaa", "bbb"]
    assert len(finished) == 2


def test_cancel_when_idle_is_harmless():
    controller, overlay, _scheduler, _armed, finished = make_controller()
    controller.cancel()
    assert finished == []
    assert overlay.calls == []


def test_send_keys_flag_reaches_the_typing_engine():
    typed = []
    controller, _overlay, scheduler, _armed, _finished = make_controller(
        cfg={"countdown_ms": 0}, typed_log=typed)
    controller.start("login", "admin{tab}pw", 4321, send_keys=True)
    scheduler.run_all()

    assert typed[0][1]["send_keys"] is True


def test_send_keys_defaults_to_off():
    typed = []
    controller, _overlay, scheduler, _armed, _finished = make_controller(
        cfg={"countdown_ms": 0}, typed_log=typed)
    controller.start("json", '{"port": 3389}', 4321)
    scheduler.run_all()

    assert typed[0][1]["send_keys"] is False


def test_bad_token_shows_a_message_that_leaks_no_body_text():
    controller, overlay, scheduler, _armed, finished = make_controller(
        cfg={"countdown_ms": 0},
        type_result=winput.TypeResult("badtoken", 0, 0, "{ctrl+hunter2} names a key ..."))
    controller.start("login", "{ctrl+hunter2}", 4321, send_keys=True)
    scheduler.run_all()

    assert finished[0].status == "badtoken"
    kind, message = overlay.calls[-1]
    assert kind == "error"
    assert message == paste.BAD_TOKEN_MESSAGE
    assert "hunter2" not in message
