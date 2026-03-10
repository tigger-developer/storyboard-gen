# ABOUTME: Editable per-scene YAML editor for storyboard-gen GUI.
# ABOUTME: Extracts/replaces scene blocks from project.yaml preserving formatting.

import logging
import re
from pathlib import Path

import yaml
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from storyboard_gen.gui.yaml_viewer import YamlHighlighter

logger = logging.getLogger(__name__)


def _find_scene_boundaries(
    lines: list[str],
) -> list[tuple[int, int, str | None]]:
    """Find start/end line indices and scene numbers for each scene block.

    Works with both hand-written YAML (``- number: 1``) and
    ``yaml.dump`` output where keys may be sorted alphabetically.

    Args:
        lines: Lines of the YAML file (with line endings).

    Returns:
        List of (start_idx, end_idx, scene_number) tuples.
        scene_number is None if no ``number:`` key was found in the block.
    """
    # First find the scenes: section
    scenes_start = None
    scenes_indent = None
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)scenes:\s*$", line)
        if m:
            scenes_start = i + 1
            scenes_indent = len(m.group(1))
            break

    if scenes_start is None:
        return []

    # Find list item boundaries (lines starting with "- " at the scene indent level)
    list_marker = re.compile(r"^(\s*)-\s+\S")
    number_pattern = re.compile(r"^\s+number:\s+(\S+)")
    inline_number = re.compile(r"^\s*-\s+number:\s+(\S+)")

    blocks: list[tuple[int, int, str | None]] = []
    current_start: int | None = None
    item_indent: int | None = None

    for i in range(scenes_start, len(lines)):
        line = lines[i]
        stripped = line.rstrip()

        # Check if we've left the scenes section (same or less indent, non-blank, non-comment)
        if stripped and not stripped.lstrip().startswith("#"):
            line_indent = len(line) - len(line.lstrip())
            if scenes_indent is not None and line_indent <= scenes_indent:
                if not line.lstrip().startswith("-"):
                    # End of scenes section
                    if current_start is not None:
                        blocks.append((current_start, i, None))
                    break

        m = list_marker.match(line)
        if m:
            marker_indent = len(m.group(1))
            if item_indent is None:
                item_indent = marker_indent
            if marker_indent == item_indent:
                if current_start is not None:
                    blocks.append((current_start, i, None))
                current_start = i
    else:
        # Reached end of file
        if current_start is not None:
            blocks.append((current_start, len(lines), None))

    # Now find the number: key within each block
    result = []
    for start, end, _ in blocks:
        scene_num = None
        for j in range(start, end):
            # Check for "- number: N" (inline) on the first line
            m = inline_number.match(lines[j])
            if m:
                scene_num = str(m.group(1))
                break
            # Check for "  number: N" (subsequent line)
            m = number_pattern.match(lines[j])
            if m:
                scene_num = str(m.group(1))
                break
        result.append((start, end, scene_num))

    return result


def extract_scene_yaml(yaml_path: Path, scene_number: str) -> str | None:
    """Extract the raw YAML block for a specific scene from project.yaml.

    Finds the scene by its ``number:`` key and extracts all lines for
    that scene block. Works with both hand-written and machine-generated
    YAML formats.

    Args:
        yaml_path: Path to project.yaml.
        scene_number: The scene number to extract (as string).

    Returns:
        The raw YAML block text, or None if the scene is not found.
    """
    content = yaml_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    for start, end, num in _find_scene_boundaries(lines):
        if str(num) == str(scene_number):
            return "".join(lines[start:end])

    return None


def replace_scene_yaml(yaml_path: Path, scene_number: str, new_block: str) -> bool:
    """Replace a scene's YAML block in project.yaml.

    Finds the scene block boundaries and replaces it with the new text.
    Validates the resulting YAML before writing.

    Args:
        yaml_path: Path to project.yaml.
        scene_number: The scene number to replace.
        new_block: The replacement YAML block text.

    Returns:
        True if replacement succeeded, False if scene not found.

    Raises:
        yaml.YAMLError: If the resulting file is not valid YAML.
    """
    content = yaml_path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    boundaries = _find_scene_boundaries(lines)

    start_idx = None
    end_idx = None
    for start, end, num in boundaries:
        if str(num) == str(scene_number):
            start_idx = start
            end_idx = end
            break

    if start_idx is None:
        return False

    # Build the new content
    new_lines = lines[:start_idx]
    # Ensure new_block ends with newline
    if new_block and not new_block.endswith("\n"):
        new_block += "\n"
    new_lines.append(new_block)
    new_lines.extend(lines[end_idx:])

    new_content = "".join(new_lines)

    # Validate the result is still valid YAML
    yaml.safe_load(new_content)

    yaml_path.write_text(new_content, encoding="utf-8")
    return True


class SceneYamlEditor(QWidget):
    """Editable YAML editor for a single scene with syntax highlighting.

    Shows the raw YAML block for the selected scene, allows editing,
    and saves changes back to project.yaml with validation.
    """

    scene_modified = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._yaml_path: Path | None = None
        self._scene_number: str | None = None
        self._original_text: str = ""

        # Editable text area
        self.text_edit = QTextEdit()
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Monospace font (same as YamlViewer)
        font = QFont("Menlo, Consolas, monospace", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(font)

        # Dark theme (same as YamlViewer)
        self.text_edit.setStyleSheet(
            "QTextEdit { background-color: #1e1e1e; color: #d4d4d4; }"
        )

        # Syntax highlighter
        self._highlighter = YamlHighlighter(self.text_edit.document())

        # Save button and status label
        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedWidth(80)
        self._save_btn.clicked.connect(self._save)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888; padding-left: 10px;")

        # Bottom bar with save button and status
        bottom_bar = QHBoxLayout()
        bottom_bar.addWidget(self._save_btn)
        bottom_bar.addWidget(self._status_label, stretch=1)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_edit)
        layout.addLayout(bottom_bar)
        self.setLayout(layout)

    def load_scene(self, scene_number: str, yaml_path: Path) -> None:
        """Load and display the YAML block for a specific scene.

        Args:
            scene_number: The scene number to load.
            yaml_path: Path to project.yaml.
        """
        self._yaml_path = yaml_path
        self._scene_number = scene_number
        self._status_label.setText("")

        block = extract_scene_yaml(yaml_path, scene_number)
        if block is None:
            self.text_edit.setPlainText(
                f"# Scene {scene_number} not found in {yaml_path.name}"
            )
            self._original_text = ""
            self._save_btn.setEnabled(False)
            return

        self.text_edit.setPlainText(block)
        self._original_text = block
        self._save_btn.setEnabled(True)

    def is_dirty(self) -> bool:
        """Return True if the editor content differs from the loaded text."""
        return self.text_edit.toPlainText() != self._original_text

    def _save(self) -> None:
        """Save the edited YAML block back to project.yaml."""
        if not self._yaml_path or not self._scene_number:
            return

        new_text = self.text_edit.toPlainText()

        # Validate the edited block is parseable YAML
        try:
            yaml.safe_load(new_text)
        except yaml.YAMLError as exc:
            self._status_label.setText(f"Error: Invalid YAML — {exc}")
            self._status_label.setStyleSheet("color: #f44; padding-left: 10px;")
            return

        try:
            result = replace_scene_yaml(self._yaml_path, self._scene_number, new_text)
        except yaml.YAMLError as exc:
            self._status_label.setText(f"Error: Invalid YAML — {exc}")
            self._status_label.setStyleSheet("color: #f44; padding-left: 10px;")
            return

        if result:
            self._original_text = new_text
            self._status_label.setText("Saved")
            self._status_label.setStyleSheet("color: #6a6; padding-left: 10px;")
            self.scene_modified.emit()
        else:
            self._status_label.setText("Error: Scene not found")
            self._status_label.setStyleSheet("color: #f44; padding-left: 10px;")
