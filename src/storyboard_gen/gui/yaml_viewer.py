# ABOUTME: Read-only YAML viewer with syntax highlighting for storyboard-gen GUI.
# ABOUTME: Uses QSyntaxHighlighter to colour-code keys, values, comments, and strings.

import re
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QShortcut,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from storyboard_gen.gui.settings import MAX_FONT_SIZE, MIN_FONT_SIZE


class YamlHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for YAML content.

    Highlights keys, string values, comments, numbers, and booleans.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._build_rules()

    def _build_rules(self) -> None:
        """Set up the highlighting rules."""
        # Comments: # to end of line
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6a9955"))
        comment_fmt.setFontItalic(True)
        self._rules.append((re.compile(r"#.*$"), comment_fmt))

        # Keys: word followed by colon (before the colon)
        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor("#569cd6"))
        key_fmt.setFontWeight(QFont.Weight.Bold)
        self._rules.append((re.compile(r"^\s*[\w@_.-]+(?=\s*:)"), key_fmt))

        # Quoted strings: "..." or '...'
        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#ce9178"))
        self._rules.append((re.compile(r'"[^"]*"'), string_fmt))
        self._rules.append((re.compile(r"'[^']*'"), string_fmt))

        # Numbers
        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("#b5cea8"))
        self._rules.append((re.compile(r"\b\d+(\.\d+)?\b"), number_fmt))

        # Booleans and nulls
        bool_fmt = QTextCharFormat()
        bool_fmt.setForeground(QColor("#569cd6"))
        self._rules.append(
            (re.compile(r"\b(true|false|yes|no|null|none)\b", re.IGNORECASE), bool_fmt)
        )

        # List markers
        marker_fmt = QTextCharFormat()
        marker_fmt.setForeground(QColor("#d4d4d4"))
        marker_fmt.setFontWeight(QFont.Weight.Bold)
        self._rules.append((re.compile(r"^\s*-\s"), marker_fmt))

    def highlightBlock(self, text: str) -> None:
        """Apply highlighting rules to a single line of text."""
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, fmt)


class YamlViewer(QWidget):
    """Read-only viewer for YAML files with syntax highlighting."""

    font_size_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Monospace font
        font = QFont("Menlo, Consolas, monospace", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(font)

        # Dark background for code viewer feel
        self.text_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )

        self._highlighter = YamlHighlighter(self.text_edit.document())

        # Font size keyboard shortcuts (Ctrl maps to Cmd on macOS)
        self._shortcut_zoom_in = QShortcut(QKeySequence("Ctrl+="), self)
        self._shortcut_zoom_in.activated.connect(self._increase_font)
        self._shortcut_zoom_in2 = QShortcut(QKeySequence("Ctrl+Shift+="), self)
        self._shortcut_zoom_in2.activated.connect(self._increase_font)
        self._shortcut_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        self._shortcut_zoom_out.activated.connect(self._decrease_font)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

    def load_file(self, path: Path) -> None:
        """Load and display a YAML file.

        Args:
            path: Path to the YAML file.
        """
        if not path.exists():
            self.text_edit.setPlainText(f"File not found: {path}")
            return
        content = path.read_text(encoding="utf-8")
        self.text_edit.setPlainText(content)

    def set_content(self, text: str) -> None:
        """Display YAML content from a string.

        Args:
            text: YAML content to display.
        """
        self.text_edit.setPlainText(text)

    def set_font_size(self, size: int) -> None:
        """Set the viewer font size, clamped to MIN_FONT_SIZE–MAX_FONT_SIZE.

        Args:
            size: Desired font point size.
        """
        clamped = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
        font = self.text_edit.font()
        font.setPointSize(clamped)
        self.text_edit.setFont(font)

    def _increase_font(self) -> None:
        """Increase font size by 1pt and emit font_size_changed."""
        new_size = self.text_edit.font().pointSize() + 1
        self.set_font_size(new_size)
        self.font_size_changed.emit(self.text_edit.font().pointSize())

    def _decrease_font(self) -> None:
        """Decrease font size by 1pt and emit font_size_changed."""
        new_size = self.text_edit.font().pointSize() - 1
        self.set_font_size(new_size)
        self.font_size_changed.emit(self.text_edit.font().pointSize())
