"""Regression tests for two wiring defects found in review of Task 15's
unpaster/main.py:

1. post_to_ui was `lambda fn: QTimer.singleShot(0, fn)`. QTimer.singleShot
   homes its timer to the *calling* thread and only fires if that thread
   runs a Qt event loop. PasteController calls post_to_ui from the plain
   threading.Thread started by run_async (the typing worker), which never
   runs a Qt event loop, so the callback was never delivered: _finish()
   never ran, controller.busy stayed True forever, and the hotkey/"Test
   type" button were dead for the rest of the session after one paste.
   Fixed by routing post_to_ui through HookBridge.ui_call, a queued Qt
   signal on a QObject that lives on the main thread -- the same pattern
   already used for the keyboard hook's callbacks.

2. _on_hotkey guarded only on controller.busy, which stays False for the
   entire time the palette is open waiting for a selection. Holding the
   hotkey's last key slightly too long (OS key repeat; HookLogic does not
   de-duplicate it) fired _on_hotkey a second time while the palette had
   already taken the foreground, overwriting _target_hwnd with the
   palette's own handle -- so the snippet got typed into the palette
   instead of the originally focused window. Fixed by also checking
   self.palette.isVisible().

Both tests run headlessly (QT_QPA_PLATFORM=offscreen) and neither calls
UnpasterApp.start() or main() -- start() installs a real global keyboard
hook and shows the tray icon, and main() acquires the real single-instance
mutex and runs the event loop.
"""

from __future__ import annotations

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from unpaster import main


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def unpaster(app):
    instance = main.UnpasterApp(app)
    try:
        yield instance
    finally:
        instance.palette.hide()
        instance.overlay.hide_now()
        instance.tray.hide()


def test_post_to_ui_delivers_worker_thread_callback_on_main_thread(unpaster):
    """PasteController's post_to_ui callable -- exactly what main.py wired
    up as `post_to_ui=self.bridge.ui_call.emit` -- must deliver a callback
    posted from a background thread, on the main thread, once the main
    thread's event loop gets a chance to run. The wait is bounded so a
    regression (callback never delivered) fails the test instead of
    hanging it.
    """
    main_thread_id = threading.get_ident()
    done = threading.Event()
    result: dict = {}

    def record() -> None:
        result["thread_id"] = threading.get_ident()
        done.set()

    post_to_ui = unpaster.controller._post_to_ui

    def emit_from_worker() -> None:
        post_to_ui(record)

    threading.Thread(target=emit_from_worker, daemon=True).start()

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not done.is_set():
        QCoreApplication.processEvents()
        time.sleep(0.01)

    assert done.is_set(), "callback was never delivered within 3s"
    assert result["thread_id"] == main_thread_id


def test_on_hotkey_ignores_repeat_while_palette_is_visible(unpaster):
    """A second hotkey firing (e.g. from OS key-repeat) while the palette is
    already open and holding foreground must not overwrite the captured
    target window -- otherwise the paste ends up typed into the palette
    itself instead of the window that was focused before the hotkey.
    """
    sentinel_hwnd = 424242
    unpaster._target_hwnd = sentinel_hwnd
    unpaster.palette.show()
    assert unpaster.palette.isVisible()

    unpaster._on_hotkey()

    assert unpaster._target_hwnd == sentinel_hwnd


def test_windows_get_the_drawn_icon(unpaster, app):
    """Without an application icon, Qt gives windows a blank titlebar icon and
    the taskbar falls back to the interpreter's own icon."""
    assert app.windowIcon().isNull() is False
    assert unpaster.manager.windowIcon().isNull() is False


def test_app_user_model_id_is_set_without_raising():
    # Windows groups a window under the process that owns the AppUserModelID;
    # without an explicit one, a python.exe host supplies both the grouping and
    # the taskbar icon.
    assert main.set_app_user_model_id() in (True, False)
