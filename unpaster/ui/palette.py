"""The popup shown by the hotkey: search a snippet or type a one-off string."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout
)

from ..paste import PasteRequest
from ..store import Snippet, SnippetStore

SECRET_MARK = "  \U0001F512"

# A list row is normally a snippet id (a uuid4), so a NUL can never collide.
CLIPBOARD_ID = "\x00clipboard"
CLIPBOARD_LABEL = "Clipboard"

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
    """Snippets that match, then Clipboard -- an action, so a query never hides it."""
    rows = [(s.id, row_label(s)) for s in snippet_store.search(query)]
    rows.append((CLIPBOARD_ID, CLIPBOARD_LABEL))
    return rows


def clipboard_text() -> str:
    """Read the host clipboard.

    The no-clipboard rule is about the *target*: unpaster must never try to hand
    text to the remote session through the clipboard, because that channel is
    what is blocked. Reading the local clipboard as a source is the opposite --
    it is the text the user already copied and cannot paste.
    """
    from PySide6.QtGui import QGuiApplication

    board = QGuiApplication.clipboard()
    return board.text() if board is not None else ""


class PaletteWindow(QDialog):
    submitted = Signal(object)  # a paste.PasteRequest
    dismissed = Signal()

    def __init__(self, snippet_store: SnippetStore, read_clipboard=clipboard_text) -> None:
        super().__init__(None)
        self._store = snippet_store
        self._read_clipboard = read_clipboard
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
        row_id = item.data(Qt.UserRole)
        if row_id == CLIPBOARD_ID:
            self._submit_clipboard()
            return
        snippet = self._store.get(row_id)
        self._finish()
        self.submitted.emit(PasteRequest(
            name=snippet.name,
            text=snippet.body,
            send_keys=snippet.send_keys,
            method=snippet.method,
            newline_mode=snippet.newline_mode,
        ))

    def _submit_clipboard(self) -> None:
        # Read at submit time, not at open: whatever is on the clipboard now is
        # what the user means.
        text = self._read_clipboard()
        if not text:
            return
        self._finish()
        # Like free text: literal and following Settings. Clipboard content is
        # arbitrary, so a stray brace must not become a {key} token.
        self.submitted.emit(PasteRequest(name="clipboard", text=text))

    def _submit_free_text(self) -> None:
        if self._closing:
            return
        text = self.free_text.text()
        if not text:
            return
        self._finish()
        # Free text is always literal and always follows Settings: nobody types
        # {ctrl+a} into the palette expecting a chord, and a stray brace should
        # never be a parse error.
        self.submitted.emit(PasteRequest(name="free text", text=text))

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
