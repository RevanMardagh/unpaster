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
