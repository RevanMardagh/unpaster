from unpaster import focus


class FakeApi:
    def __init__(self, set_results, bring_result=False, attach_result=True):
        self.set_results = list(set_results)
        self.bring_result = bring_result
        self.attach_result = attach_result
        self.calls = []

    def set_foreground(self, hwnd):
        self.calls.append(("set_foreground", hwnd))
        return self.set_results.pop(0)

    def window_thread_id(self, hwnd):
        return 111

    def current_thread_id(self):
        return 222

    def attach_thread_input(self, source, target, attach):
        self.calls.append(("attach", source, target, attach))
        return self.attach_result

    def bring_to_top(self, hwnd):
        self.calls.append(("bring_to_top", hwnd))
        return self.bring_result


def test_first_attempt_succeeds_without_escalation():
    api = FakeApi(set_results=[True])
    assert focus.restore_foreground(1234, api=api) is True
    assert api.calls == [("set_foreground", 1234)]


def test_escalates_to_attach_thread_input():
    api = FakeApi(set_results=[False, True])
    assert focus.restore_foreground(1234, api=api) is True
    assert api.calls == [
        ("set_foreground", 1234),
        ("attach", 222, 111, True),
        ("set_foreground", 1234),
        ("attach", 222, 111, False),
    ]


def test_detaches_even_when_retry_fails():
    api = FakeApi(set_results=[False, False], bring_result=True)
    assert focus.restore_foreground(1234, api=api) is True
    assert ("attach", 222, 111, False) in api.calls
    assert api.calls[-1] == ("bring_to_top", 1234)


def test_returns_false_when_every_escalation_fails():
    api = FakeApi(set_results=[False, False], bring_result=False)
    assert focus.restore_foreground(1234, api=api) is False


def test_zero_handle_is_rejected_without_calling_the_api():
    api = FakeApi(set_results=[True])
    assert focus.restore_foreground(0, api=api) is False
    assert api.calls == []


def test_same_thread_skips_attach():
    class SameThreadApi(FakeApi):
        def current_thread_id(self):
            return 111

    api = SameThreadApi(set_results=[False], bring_result=True)
    assert focus.restore_foreground(1234, api=api) is True
    assert not any(call[0] == "attach" for call in api.calls)


def test_get_foreground_returns_an_integer():
    assert isinstance(focus.get_foreground(), int)


class DonorApi(FakeApi):
    """Thread ids differ per window, so a test can tell which one was asked."""

    THREADS = {1234: 999, 5678: 111}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thread_queries = []

    def window_thread_id(self, hwnd):
        self.thread_queries.append(hwnd)
        return self.THREADS.get(hwnd, 0)


def test_take_foreground_succeeds_without_escalation():
    api = FakeApi(set_results=[True])
    assert focus.take_foreground(1234, 5678, api=api) is True
    assert api.calls == [("set_foreground", 1234)]


def test_take_foreground_borrows_the_input_queue_of_the_donor_window():
    """The donor is the window that owns the foreground, not our own window:
    Windows only lets a process activate a window when it already has input
    rights, and attaching to the foreground thread is how those are borrowed."""
    api = DonorApi(set_results=[False, True])
    assert focus.take_foreground(1234, 5678, api=api) is True
    assert api.thread_queries == [5678]
    assert api.calls == [
        ("set_foreground", 1234),
        ("attach", 222, 111, True),
        ("set_foreground", 1234),
        ("attach", 222, 111, False),
    ]


def test_take_foreground_detaches_even_when_the_retry_fails():
    api = DonorApi(set_results=[False, False], bring_result=True)
    assert focus.take_foreground(1234, 5678, api=api) is True
    assert ("attach", 222, 111, False) in api.calls
    assert api.calls[-1] == ("bring_to_top", 1234)


def test_take_foreground_falls_back_when_there_is_no_donor():
    api = DonorApi(set_results=[False], bring_result=True)
    assert focus.take_foreground(1234, 0, api=api) is True
    assert not any(call[0] == "attach" for call in api.calls)


def test_take_foreground_returns_false_when_every_escalation_fails():
    api = DonorApi(set_results=[False, False], bring_result=False)
    assert focus.take_foreground(1234, 5678, api=api) is False


def test_take_foreground_rejects_a_zero_handle_without_calling_the_api():
    api = FakeApi(set_results=[True])
    assert focus.take_foreground(0, 5678, api=api) is False
    assert api.calls == []
