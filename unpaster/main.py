"""Entry point: tray icon, hotkey wiring, and window lifetimes."""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import config, focus, hotkey, paste, store
from .ui.icon import tray_icon
from .ui.manager import ManagerWindow
from .ui.overlay import OverlayWindow
from .ui.palette import PaletteWindow

MUTEX_NAME = "unpaster-single-instance-4f21c0"
TEST_TEXT = "unpaster test 12345 - the quick brown fox"

ERROR_ALREADY_EXISTS = 183

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL


def acquire_single_instance(name: str = MUTEX_NAME):
    handle = _kernel32.CreateMutexW(None, True, name)
    if not handle:
        return None
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return None
    return handle


def release_single_instance(handle) -> None:
    if handle:
        _kernel32.CloseHandle(handle)


class HookBridge(QObject):
    """Carries hook-thread events onto the Qt main thread."""

    hotkey_pressed = Signal()
    escape_pressed = Signal()


class UnpasterApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.cfg, warnings = config.load(config.config_path())
        self.store, store_warnings = store.SnippetStore.load(store.snippets_path())
        self._pending_warnings = warnings + store_warnings
        self._balloon_shown = False
        self._target_hwnd = 0

        self.overlay = OverlayWindow()
        self.palette = PaletteWindow(self.store)
        self.manager = ManagerWindow(self.store, self.cfg,
                                     on_config_changed=self._apply_config,
                                     on_quit=self.quit)
        self.manager.hidden_to_tray = self._on_hidden_to_tray
        self.manager.test_requested = self._run_test_paste

        self.controller = paste.PasteController(
            overlay=self.overlay,
            set_armed=self._set_armed,
            get_config=lambda: self.cfg,
            schedule=lambda delay_ms, fn: QTimer.singleShot(delay_ms, fn),
            run_async=self._run_async,
            post_to_ui=lambda fn: QTimer.singleShot(0, fn),
        )

        self.bridge = HookBridge()
        self.bridge.hotkey_pressed.connect(self._on_hotkey)
        self.bridge.escape_pressed.connect(self.controller.cancel)

        self.hook = hotkey.KeyboardHook(
            self._parsed_hotkey(),
            on_hotkey=self.bridge.hotkey_pressed.emit,
            on_escape=self.bridge.escape_pressed.emit,
        )

        self.tray = self._build_tray()
        self.palette.submitted.connect(self._on_palette_submitted)

    # -- startup -----------------------------------------------------------

    def start(self) -> None:
        self.tray.show()
        try:
            self.hook.start()
        except hotkey.HookInstallError as exc:
            self._pending_warnings.append(
                f"The global hotkey could not be installed ({exc}). "
                "unpaster still works from the tray menu."
            )
        for warning in self._pending_warnings:
            self.tray.showMessage("unpaster", warning, QSystemTrayIcon.Warning, 8000)
        self._pending_warnings.clear()

    def quit(self) -> None:
        self.hook.stop()
        self.overlay.hide_now()
        self.tray.hide()
        self.app.quit()

    # -- tray --------------------------------------------------------------

    def _build_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(tray_icon())
        tray.setToolTip("unpaster")

        menu = QMenu()
        menu.addAction("Open", self.manager.show_snippets)
        menu.addAction("Paste now", self._on_hotkey)
        menu.addAction("Settings", self.manager.show_settings)
        menu.addSeparator()
        menu.addAction("Quit", self.manager.request_quit)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        return tray

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.manager.show_snippets()

    def _on_hidden_to_tray(self) -> None:
        if self._balloon_shown:
            return
        self._balloon_shown = True
        self.tray.showMessage(
            "unpaster is still running",
            "Right-click the tray icon to quit.",
            QSystemTrayIcon.Information, 5000,
        )

    # -- paste flow --------------------------------------------------------

    def _on_hotkey(self) -> None:
        if self.controller.busy:
            return
        self._target_hwnd = focus.get_foreground()
        self.overlay.move_to_screen_of(self._target_hwnd)
        self.palette.open_palette()

    def _on_palette_submitted(self, name: str, text: str) -> None:
        self.controller.start(name, text, self._target_hwnd)

    def _run_test_paste(self) -> None:
        self._target_hwnd = int(self.manager.winId())
        self.overlay.move_to_screen_of(self._target_hwnd)
        self.controller.start("test type", TEST_TEXT, self._target_hwnd)

    def _set_armed(self, armed: bool) -> None:
        self.hook.set_armed(armed)

    @staticmethod
    def _run_async(fn) -> None:
        threading.Thread(target=fn, name="unpaster-type", daemon=True).start()

    # -- settings ----------------------------------------------------------

    def _parsed_hotkey(self) -> hotkey.Hotkey:
        try:
            return hotkey.parse_hotkey(self.cfg["hotkey"])
        except hotkey.HotkeyParseError:
            self._pending_warnings.append(
                f"Hotkey {self.cfg['hotkey']!r} is not valid; using "
                f"{config.DEFAULTS['hotkey']} instead."
            )
            self.cfg["hotkey"] = config.DEFAULTS["hotkey"]
            return hotkey.parse_hotkey(self.cfg["hotkey"])

    def _apply_config(self, cfg: dict) -> None:
        self.cfg = cfg
        config.save(config.config_path(), cfg)
        self.hook.set_hotkey(hotkey.parse_hotkey(cfg["hotkey"]))


def main() -> int:
    handle = acquire_single_instance()
    if handle is None:
        app = QApplication(sys.argv)
        QMessageBox.information(None, "unpaster", "unpaster is already running.")
        del app
        return 0

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("unpaster")

    unpaster = UnpasterApp(app)
    unpaster.start()
    try:
        return app.exec()
    finally:
        release_single_instance(handle)


if __name__ == "__main__":
    raise SystemExit(main())
