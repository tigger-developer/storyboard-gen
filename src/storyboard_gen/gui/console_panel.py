# ABOUTME: Console panel widget for log output display.
# ABOUTME: Includes a custom logging.Handler that bridges Python logging to Qt signals.

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget


class _LogSignalBridge(QObject):
    """Bridge object that carries log messages as Qt signals.

    QThread requires signal sources to be QObject subclasses.
    This bridge lets QtLogHandler emit signals without itself
    being a QObject (logging.Handler doesn't support multiple
    inheritance with QObject cleanly).
    """

    message = Signal(str)


class QtLogHandler(logging.Handler):
    """Logging handler that emits formatted log messages via a Qt signal.

    Connect to ``handler.log_signal.message`` to receive log strings.
    """

    def __init__(self):
        super().__init__()
        self.log_signal = _LogSignalBridge()
        self.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        """Format the record and emit it via the Qt signal."""
        msg = self.format(record)
        self.log_signal.message.emit(msg)


class ConsolePanel(QWidget):
    """Read-only text panel that displays log messages."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def append_message(self, text: str) -> None:
        """Append a log message and scroll to the bottom."""
        self.text_edit.append(text)
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        """Clear all log messages."""
        self.text_edit.clear()
