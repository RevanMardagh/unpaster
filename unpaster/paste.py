"""Sequences one paste: restore focus, count down, type, report.

No Qt and no Windows calls are made directly. Timers, threads, and the
foreground restore are injected, which keeps the ordering rules -- especially
"never type when focus restore failed" -- testable headless.
"""

from __future__ import annotations

import threading

from . import focus, winput

SETTLE_MS = 120

FOCUS_FAILED_MESSAGE = (
    "Could not bring the target window back to the front. Nothing was typed."
)

UNMAPPABLE_MESSAGE = (
    "A character in the text has no key on the current keyboard layout."
)


class PasteController:
    def __init__(
        self,
        overlay,
        set_armed,
        get_config,
        schedule,
        run_async,
        post_to_ui,
        restore_foreground=focus.restore_foreground,
        type_text=winput.type_text,
        on_finished=None,
    ) -> None:
        self._overlay = overlay
        self._set_armed = set_armed
        self._get_config = get_config
        self._schedule = schedule
        self._run_async = run_async
        self._post_to_ui = post_to_ui
        self._restore_foreground = restore_foreground
        self._type_text = type_text
        self._on_finished = on_finished

        self._busy = False
        self._cancel = threading.Event()
        self._name = ""
        self._text = ""
        self._cfg: dict = {}
        self._remaining = 0

    @property
    def busy(self) -> bool:
        return self._busy

    # -- entry points ------------------------------------------------------

    def start(self, name: str, text: str, target_hwnd: int) -> None:
        if self._busy:
            return

        self._busy = True
        self._cancel = threading.Event()
        self._name = name
        self._text = text
        self._cfg = dict(self._get_config())
        self._set_armed(True)

        if not self._restore_foreground(target_hwnd):
            self._show_error(FOCUS_FAILED_MESSAGE)
            self._finish(winput.TypeResult("focus-failed", 0, 0, FOCUS_FAILED_MESSAGE),
                         already_reported=True)
            return

        countdown_ms = int(self._cfg.get("countdown_ms", 0))
        if countdown_ms <= 0:
            self._schedule(SETTLE_MS, self._begin_typing)
            return

        self._remaining = max(1, round(countdown_ms / 1000))
        self._tick()

    def cancel(self) -> None:
        if not self._busy:
            return
        self._cancel.set()

    # -- countdown ---------------------------------------------------------

    def _tick(self) -> None:
        if self._cancel.is_set():
            self._finish(winput.TypeResult("cancelled", 0, 0))
            return
        if self._remaining <= 0:
            self._begin_typing()
            return

        self._show_countdown(self._remaining)
        self._remaining -= 1
        self._schedule(1000, self._tick)

    # -- typing ------------------------------------------------------------

    def _begin_typing(self) -> None:
        if self._cancel.is_set():
            self._finish(winput.TypeResult("cancelled", 0, 0))
            return
        self._run_async(self._type_worker)

    def _type_worker(self) -> None:
        result = self._type_text(
            self._text,
            method=self._cfg.get("method", "unicode"),
            newline_mode=self._cfg.get("newline_mode", "enter"),
            char_delay_ms=int(self._cfg.get("char_delay_ms", 12)),
            cancel=self._cancel,
            progress=self._on_progress,
        )
        self._post_to_ui(lambda: self._finish(result))

    def _on_progress(self, typed: int, total: int) -> None:
        self._post_to_ui(lambda: self._show_progress(typed, total))

    # -- completion --------------------------------------------------------

    def _finish(self, result, already_reported: bool = False) -> None:
        if not already_reported:
            if result.status == "done":
                self._show_done()
            elif result.status == "cancelled":
                self._show_cancelled()
            elif result.status == "unmappable":
                self._show_error(UNMAPPABLE_MESSAGE)
            else:
                self._show_error(result.detail or result.status)

        self._set_armed(False)
        self._busy = False
        if self._on_finished is not None:
            self._on_finished(result)

    # -- overlay gating ----------------------------------------------------

    def _overlay_enabled(self) -> bool:
        return bool(self._cfg.get("overlay_enabled", True))

    def _show_countdown(self, seconds: int) -> None:
        if self._overlay_enabled():
            self._overlay.show_countdown(self._name, seconds)

    def _show_progress(self, typed: int, total: int) -> None:
        if self._overlay_enabled():
            self._overlay.show_progress(self._name, typed, total)

    def _show_done(self) -> None:
        if self._overlay_enabled():
            self._overlay.show_done()

    def _show_cancelled(self) -> None:
        if self._overlay_enabled():
            self._overlay.show_cancelled()

    def _show_error(self, message: str) -> None:
        if self._overlay_enabled():
            self._overlay.show_error(message)
