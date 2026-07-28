"""The popup shown by the hotkey: search a snippet or type a one-off string."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout
)

from ..store import Snippet, SnippetStore

SECRET_MARK = "  \U0001F512"

STYLE = """
QDialog { background: #14161c; border: 1px solid #333a48; border-radius: 10px; }
QLineEdit {
    background: #1c1f27; color: #ebeef5; border: 1px solid #333a48;
    border-radius: 6px; padding: 7px 9px; font-size: 13px;
}
QLineEdit:focus { border-color: #78c8ff; }
QListWidget {
    background: #1c1f27; color: #ebeef5; border: 1px solid #333a48;
    border-radius: 6px; font-size: 13px; outline: none;
}
QListWidget::item { padding: 5px 8px; }
QListWidget::item:selected { background: #2b4f6b; color: #ffffff; }
QLabel { color: #969eaf; font-size: 11px; }
"""


def row_label(snippet: Snippet) -> str:
    """Name only. The body may be a secret and is never rendered here."""
    return snippet.name + (SECRET_MARK if snippet.secret else "")


def palette_rows(snippet_store: SnippetStore, query: str) -> list[tuple[str, str]]:
    return [(s.id, row_label(s)) for s in snippet_store.search(query)]


class PaletteWindow(QDialog):
    submitted = Signal(str, str, bool)  # display name, text to type, send keys
    dismissed = Signal()

    def __init__(self, snippet_store: SnippetStore) -> None:
        super().__init__(None)
        self._store = snippet_store
        self._closing = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(420)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("search snippets")
        self.list = QListWidget(self)
        self.list.setFixedHeight(190)
        self.free_text = QLineEdit(self)
        self.free_text.setPlaceholderText("or type one-off text here")
        hint = QLabel("Enter types the selection · Tab switches · Esc cancels", self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        layout.addWidget(self.free_text)
        layout.addWidget(hint)

        self.search.textChanged.connect(self._refresh)
        self.search.returnPressed.connect(self._submit_selected)
        self.free_text.returnPressed.connect(self._submit_free_text)
        self.list.itemActivated.connect(lambda _item: self._submit_selected())

    # -- lifecycle ---------------------------------------------------------

    def open_palette(self) -> None:
        self._closing = False
        self.search.clear()
        self.free_text.clear()
        self._refresh("")
        self._center_on_cursor_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    def _center_on_cursor_screen(self) -> None:
        from PySide6.QtGui import QCursor, QGuiApplication

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        rect = screen.geometry()
        self.adjustSize()
        self.move(rect.x() + (rect.width() - self.width()) // 2,
                  rect.y() + (rect.height() - self.height()) // 3)

    def _finish(self) -> None:
        self._closing = True
        self.hide()

    # -- contents ----------------------------------------------------------

    def _refresh(self, query: str = "") -> None:
        self.list.clear()
        for snippet_id, label in palette_rows(self._store, query):
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, snippet_id)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    # -- submission --------------------------------------------------------

    def _submit_selected(self) -> None:
        if self._closing:
            return
        item = self.list.currentItem()
        if item is None:
            return
        snippet = self._store.get(item.data(Qt.UserRole))
        self._finish()
        self.submitted.emit(snippet.name, snippet.body, snippet.send_keys)

    def _submit_free_text(self) -> None:
        if self._closing:
            return
        text = self.free_text.text()
        if not text:
            return
        self._finish()
        # Free text is always literal: nobody types {ctrl+a} into the palette
        # expecting a chord, and a stray brace should never be a parse error.
        self.submitted.emit("free text", text, False)

    # -- input handling ----------------------------------------------------

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key_Escape:
            self._finish()
            self.dismissed.emit()
            return
        if key in (Qt.Key_Down, Qt.Key_Up) and self.search.hasFocus() and self.list.count():
            step = 1 if key == Qt.Key_Down else -1
            row = (self.list.currentRow() + step) % self.list.count()
            self.list.setCurrentRow(row)
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._dismiss_if_inactive()

    def event(self, event):
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.WindowDeactivate:
            self._dismiss_if_inactive()
        return super().event(event)

    def _dismiss_if_inactive(self) -> None:
        if self.isVisible() and not self._closing:
            self._finish()
            self.dismissed.emit()
