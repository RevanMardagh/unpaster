"""Manager window: snippet editing and settings."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget
)

from .. import autostart, config, hotkey, winput
from ..store import SnippetStore
from .palette import SECRET_MARK

LIST_BUTTON_SIZE = 28
REVEAL_BUTTON_WIDTH = 68

EDITABLE_KEYS = (
    "hotkey", "countdown_ms", "char_delay_ms", "method",
    "newline_mode", "overlay_enabled", "close_to_tray", "autostart",
)

MASK = "•" * 12

CLOSE_TO_TRAY_TOOLTIP = (
    "When off, closing this window quits unpaster entirely and the hotkey stops working."
)


def config_to_form(cfg: dict) -> dict:
    return {key: cfg.get(key, config.DEFAULTS[key]) for key in EDITABLE_KEYS}


def form_to_config(base: dict, form: dict) -> tuple[dict, list[str]]:
    """Merge form values onto base and validate, so the UI cannot write junk."""
    merged = dict(base)
    merged.update({key: value for key, value in form.items() if key in EDITABLE_KEYS})
    return config.validate(merged)


class HotkeyEdit(QLineEdit):
    """Captures a key combination instead of accepting typed text."""

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setReadOnly(True)
        self.setPlaceholderText("click, then press a combination (F1-F24 may be alone)")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
            return

        parts = []
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.AltModifier:
            parts.append("alt")
        if modifiers & Qt.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.MetaModifier:
            parts.append("win")

        name = _key_name(key)
        if name is None:
            return
        parts.append(name)
        # No modifier check here: parse_hotkey decides, so F1-F24 can be
        # captured on their own while other bare keys are rejected below.

        try:
            combo = hotkey.parse_hotkey("+".join(parts))
        except hotkey.HotkeyParseError:
            return
        self.setText(hotkey.format_hotkey(combo))


def _key_name(key: int) -> str | None:
    if Qt.Key_A <= key <= Qt.Key_Z:
        return chr(ord("a") + key - Qt.Key_A)
    if Qt.Key_0 <= key <= Qt.Key_9:
        return chr(ord("0") + key - Qt.Key_0)
    if Qt.Key_F1 <= key <= Qt.Key_F24:
        return f"f{key - Qt.Key_F1 + 1}"
    return {
        Qt.Key_Space: "space", Qt.Key_Tab: "tab", Qt.Key_Return: "enter",
        Qt.Key_Enter: "enter", Qt.Key_Insert: "insert", Qt.Key_Delete: "delete",
        Qt.Key_Home: "home", Qt.Key_End: "end", Qt.Key_PageUp: "pageup",
        Qt.Key_PageDown: "pagedown", Qt.Key_Left: "left", Qt.Key_Right: "right",
        Qt.Key_Up: "up", Qt.Key_Down: "down", Qt.Key_Backspace: "backspace",
    }.get(key)


class ManagerWindow(QMainWindow):
    def __init__(self, snippet_store: SnippetStore, cfg: dict,
                 on_config_changed, on_quit) -> None:
        super().__init__()
        self._store = snippet_store
        self._cfg = dict(cfg)
        self._on_config_changed = on_config_changed
        self._on_quit = on_quit
        self._quitting = False
        self._revealed = False
        self._current_id: str | None = None

        self.setWindowTitle("unpaster")
        self.resize(680, 480)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_snippets_tab(), "Snippets")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        self.setCentralWidget(self.tabs)

        self._reload_list()

    # -- snippets tab ------------------------------------------------------

    def _build_snippets_tab(self) -> QWidget:
        page = QWidget()
        self.snippet_list = QListWidget(page)
        self.snippet_list.currentItemChanged.connect(lambda *_: self._load_selected())

        self.name_edit = QLineEdit(page)
        self.body_edit = QPlainTextEdit(page)
        self.secret_check = QCheckBox("Secret (mask in lists, never shown in overlay)", page)
        self.keys_check = QCheckBox("Send key tokens: {ctrl+a} {enter} {wait:500}, {{ for a brace", page)
        self.keys_check.setToolTip(
            "Off by default so bodies holding JSON or shell braces type unchanged."
        )
        self.snippet_status = QLabel("", page)
        self.snippet_status.setWordWrap(True)

        # Reveal sits beside the Secret box it belongs to, kept small so it
        # reads as a view toggle rather than an action on the snippet.
        self.reveal_button = QPushButton("Reveal", page)
        self.reveal_button.setCheckable(True)
        self.reveal_button.setFixedWidth(REVEAL_BUTTON_WIDTH)
        self.reveal_button.setToolTip("Show the body of a secret snippet while editing")
        self.reveal_button.toggled.connect(self._toggle_reveal)

        secret_row = QHBoxLayout()
        secret_row.addWidget(self.secret_check)
        secret_row.addWidget(self.reveal_button)
        secret_row.addStretch(1)

        self.save_button = QPushButton("Save", page)
        self.save_button.clicked.connect(self._save_current)
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_row.addWidget(self.save_button)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Body", self.body_edit)
        form.addRow("", secret_row)
        form.addRow("", self.keys_check)
        form.addRow("", self.snippet_status)

        right = QVBoxLayout()
        right.addLayout(form)
        right.addLayout(save_row)

        layout = QHBoxLayout(page)
        layout.addLayout(self._build_list_column(page), 1)
        layout.addLayout(right, 2)
        return page

    def _build_list_column(self, page: QWidget) -> QVBoxLayout:
        """The snippet list with its own compact add/remove/reorder strip."""
        self.add_button = self._list_button(page, "+", "Add a snippet", self._add)
        self.delete_button = self._list_button(page, "−", "Delete the selected snippet",
                                               self._delete_current)
        self.up_button = self._list_button(page, "▲", "Move the selection up",
                                           lambda: self._move(-1))
        self.down_button = self._list_button(page, "▼", "Move the selection down",
                                             lambda: self._move(1))

        strip = QHBoxLayout()
        strip.setSpacing(4)
        for button in (self.add_button, self.delete_button, self.up_button, self.down_button):
            strip.addWidget(button)
        strip.addStretch(1)

        column = QVBoxLayout()
        column.addWidget(self.snippet_list)
        column.addLayout(strip)
        return column

    @staticmethod
    def _list_button(page: QWidget, label: str, tip: str, handler) -> QPushButton:
        button = QPushButton(label, page)
        button.setFixedSize(LIST_BUTTON_SIZE, LIST_BUTTON_SIZE)
        button.setToolTip(tip)
        button.setAccessibleName(tip)
        button.clicked.connect(handler)
        return button

    def _reload_list(self, select_id: str | None = None) -> None:
        self.snippet_list.blockSignals(True)
        self.snippet_list.clear()
        for snippet in self._store.snippets:
            item = QListWidgetItem(snippet.name + (SECRET_MARK if snippet.secret else ""))
            item.setData(Qt.UserRole, snippet.id)
            self.snippet_list.addItem(item)
        self.snippet_list.blockSignals(False)

        target = select_id or self._current_id
        for row in range(self.snippet_list.count()):
            if self.snippet_list.item(row).data(Qt.UserRole) == target:
                self.snippet_list.setCurrentRow(row)
                return
        if self.snippet_list.count():
            self.snippet_list.setCurrentRow(0)
        else:
            self._current_id = None
            self.name_edit.clear()
            self.body_edit.clear()

    def _load_selected(self) -> None:
        item = self.snippet_list.currentItem()
        if item is None:
            return
        self._current_id = item.data(Qt.UserRole)
        snippet = self._store.get(self._current_id)
        self.name_edit.setText(snippet.name)
        self.secret_check.setChecked(snippet.secret)
        self.keys_check.setChecked(snippet.send_keys)
        self.snippet_status.setText("")
        self.reveal_button.setChecked(False)
        self._render_body(snippet.body, snippet.secret)

    def _render_body(self, body: str, secret: bool) -> None:
        self.body_edit.setPlainText(MASK if secret and not self._revealed else body)
        self.body_edit.setReadOnly(secret and not self._revealed)

    def _toggle_reveal(self, revealed: bool) -> None:
        self._revealed = revealed
        if self._current_id:
            snippet = self._store.get(self._current_id)
            self._render_body(snippet.body, snippet.secret)

    def _add(self) -> None:
        snippet = self._store.add("new snippet", "")
        self._store.save()
        self._revealed = True
        self.reveal_button.setChecked(True)
        self._reload_list(select_id=snippet.id)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _save_current(self) -> None:
        if not self._current_id:
            return
        snippet = self._store.get(self._current_id)
        secret = self.secret_check.isChecked()
        send_keys = self.keys_check.isChecked()
        body = snippet.body
        if not self.body_edit.isReadOnly():
            body = self.body_edit.toPlainText()

        if send_keys:
            problem = winput.check_tokens(body)
            if problem is not None:
                # Refused here rather than at paste time: the body is on screen
                # now, so the exact token can be named without leaking a secret
                # into the overlay later.
                self.snippet_status.setText(f"Not saved: {problem}")
                return

        self.snippet_status.setText("")
        self._store.update(self._current_id, name=self.name_edit.text().strip() or "unnamed",
                           body=body, secret=secret, send_keys=send_keys)
        self._store.save()
        self._reload_list(select_id=self._current_id)

    def _delete_current(self) -> None:
        if not self._current_id:
            return
        snippet = self._store.get(self._current_id)
        answer = QMessageBox.question(self, "Delete snippet", f"Delete {snippet.name!r}?")
        if answer != QMessageBox.Yes:
            return
        self._store.delete(self._current_id)
        self._store.save()
        self._current_id = None
        self._reload_list()

    def _move(self, offset: int) -> None:
        if not self._current_id:
            return
        snippet = self._store.get(self._current_id)
        self._store.move(self._current_id, snippet.order + offset)
        self._store.save()
        self._reload_list(select_id=self._current_id)

    # -- settings tab ------------------------------------------------------

    def _build_settings_tab(self) -> QWidget:
        page = QWidget()
        form_values = config_to_form(self._cfg)

        self.hotkey_edit = HotkeyEdit(form_values["hotkey"], page)

        self.countdown_spin = QSpinBox(page)
        self.countdown_spin.setRange(0, 30)
        self.countdown_spin.setSuffix(" s")
        self.countdown_spin.setValue(form_values["countdown_ms"] // 1000)

        self.delay_spin = QSpinBox(page)
        self.delay_spin.setRange(0, config.CHAR_DELAY_MAX_MS)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setValue(form_values["char_delay_ms"])

        self.method_combo = QComboBox(page)
        self.method_combo.addItem("Unicode (works across keyboard layouts)", "unicode")
        self.method_combo.addItem("Scancode (fallback for old VNC viewers)", "scancode")
        self.method_combo.setCurrentIndex(config.METHODS.index(form_values["method"]))

        self.newline_combo = QComboBox(page)
        self.newline_combo.addItem("Press Enter", "enter")
        self.newline_combo.addItem("Skip", "skip")
        self.newline_combo.addItem("Type a literal line feed", "literal")
        self.newline_combo.setCurrentIndex(config.NEWLINE_MODES.index(form_values["newline_mode"]))

        self.overlay_check = QCheckBox("Show overlay", page)
        self.overlay_check.setChecked(form_values["overlay_enabled"])

        self.tray_check = QCheckBox("Close button minimizes to tray", page)
        self.tray_check.setChecked(form_values["close_to_tray"])
        self.tray_check.setToolTip(CLOSE_TO_TRAY_TOOLTIP)

        self.autostart_check = QCheckBox("Start with Windows", page)
        self.autostart_check.setChecked(form_values["autostart"])

        self.test_edit = QLineEdit(page)
        self.test_edit.setPlaceholderText("Test type writes here")
        test_button = QPushButton("Test type", page)
        test_button.clicked.connect(self._request_test)
        test_row = QHBoxLayout()
        test_row.addWidget(self.test_edit)
        test_row.addWidget(test_button)

        self.settings_status = QLabel("", page)

        form = QFormLayout()
        form.addRow("Hotkey", self.hotkey_edit)
        form.addRow("Countdown before typing", self.countdown_spin)
        form.addRow("Character delay", self.delay_spin)
        form.addRow("Type method", self.method_combo)
        form.addRow("Newline handling", self.newline_combo)
        form.addRow("", self.overlay_check)
        form.addRow("", self.tray_check)
        form.addRow("", self.autostart_check)
        form.addRow("Test", test_row)

        apply_button = QPushButton("Apply", page)
        revert_button = QPushButton("Restore defaults", page)
        apply_button.clicked.connect(self._apply_settings)
        revert_button.clicked.connect(self._restore_defaults)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(revert_button)
        buttons.addWidget(apply_button)

        layout = QVBoxLayout(page)
        layout.addLayout(form)
        layout.addWidget(self.settings_status)
        layout.addStretch(1)
        layout.addLayout(buttons)
        return page

    def _read_form(self) -> dict:
        return {
            "hotkey": self.hotkey_edit.text(),
            "countdown_ms": self.countdown_spin.value() * 1000,
            "char_delay_ms": self.delay_spin.value(),
            "method": self.method_combo.currentData(),
            "newline_mode": self.newline_combo.currentData(),
            "overlay_enabled": self.overlay_check.isChecked(),
            "close_to_tray": self.tray_check.isChecked(),
            "autostart": self.autostart_check.isChecked(),
        }

    def _write_form(self, cfg: dict) -> None:
        values = config_to_form(cfg)
        self.hotkey_edit.setText(values["hotkey"])
        self.countdown_spin.setValue(values["countdown_ms"] // 1000)
        self.delay_spin.setValue(values["char_delay_ms"])
        self.method_combo.setCurrentIndex(config.METHODS.index(values["method"]))
        self.newline_combo.setCurrentIndex(config.NEWLINE_MODES.index(values["newline_mode"]))
        self.overlay_check.setChecked(values["overlay_enabled"])
        self.tray_check.setChecked(values["close_to_tray"])
        self.autostart_check.setChecked(values["autostart"])

    def _apply_settings(self) -> None:
        merged, warnings = form_to_config(self._cfg, self._read_form())

        try:
            hotkey.parse_hotkey(merged["hotkey"])
        except hotkey.HotkeyParseError as exc:
            self.settings_status.setText(f"Hotkey not applied: {exc}")
            return

        try:
            if merged["autostart"]:
                autostart.enable()
            else:
                autostart.disable()
        except OSError as exc:
            merged["autostart"] = autostart.is_enabled()
            warnings.append(f"Could not change the Windows startup entry: {exc}")

        self._cfg = merged
        self._write_form(merged)
        self._on_config_changed(dict(merged))
        self.settings_status.setText(" ".join(warnings) if warnings else "Applied.")

    def _restore_defaults(self) -> None:
        self._write_form(config.DEFAULTS)
        self.settings_status.setText("Defaults loaded. Press Apply to keep them.")

    def _request_test(self) -> None:
        self.test_edit.clear()
        self.test_edit.setFocus()
        self.test_requested()

    def test_requested(self) -> None:
        """Overridden by main to run a real paste into the test field."""

    # -- window behaviour --------------------------------------------------

    def show_snippets(self) -> None:
        self.tabs.setCurrentIndex(0)
        self._show_front()

    def show_settings(self) -> None:
        self.tabs.setCurrentIndex(1)
        self._show_front()

    def _show_front(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def request_quit(self) -> None:
        self._quitting = True
        self.close()

    def closeEvent(self, event) -> None:
        if self._quitting or not self._cfg.get("close_to_tray", True):
            event.accept()
            self._on_quit()
            return
        event.ignore()
        self.hide()
        self.hidden_to_tray()

    def hidden_to_tray(self) -> None:
        """Overridden by main to show the one-time tray balloon."""

    def apply_external_config(self, cfg: dict) -> None:
        self._cfg = dict(cfg)
        self._write_form(self._cfg)
