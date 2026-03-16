# ABOUTME: Editable per-scene YAML editor for storyboard-gen GUI.
# ABOUTME: Extracts/replaces scene blocks from project.yaml with model override selector.

import logging
import re
from pathlib import Path

import yaml
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from storyboard_gen.gui.settings import MAX_FONT_SIZE, MIN_FONT_SIZE
from storyboard_gen.gui.yaml_viewer import YamlHighlighter
from storyboard_gen.model_registry import get_all_models

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
    font_size_changed = Signal(int)

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

        # Font size keyboard shortcuts (Ctrl maps to Cmd on macOS)
        self._shortcut_zoom_in = QShortcut(QKeySequence("Ctrl+="), self)
        self._shortcut_zoom_in.activated.connect(self._increase_font)
        self._shortcut_zoom_in2 = QShortcut(QKeySequence("Ctrl+Shift+="), self)
        self._shortcut_zoom_in2.activated.connect(self._increase_font)
        self._shortcut_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        self._shortcut_zoom_out.activated.connect(self._decrease_font)

        # --- Model override bar ---
        model_bar = QHBoxLayout()
        model_bar.addWidget(QLabel("Model:"))

        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setPlaceholderText("Project default")
        all_model_ids = sorted(get_all_models().keys())
        self._model_combo.addItems(all_model_ids)
        self._model_combo.setCurrentText("")

        completer = QCompleter(all_model_ids, self)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._model_combo.setCompleter(completer)
        self._model_combo.currentTextChanged.connect(self._on_model_text_changed)
        # Inject model into YAML when user picks from completer popup
        completer.activated.connect(self._on_model_selected)

        model_bar.addWidget(self._model_combo, stretch=1)

        self._backend_label = QLabel("")
        self._backend_label.setStyleSheet("color: #888; padding-left: 6px;")
        self._backend_label.setFixedWidth(80)
        model_bar.addWidget(self._backend_label)

        self._clear_model_btn = QPushButton("Clear")
        self._clear_model_btn.setToolTip("Remove scene-level model override")
        self._clear_model_btn.clicked.connect(self._on_clear_model)
        model_bar.addWidget(self._clear_model_btn)

        # Save button and status label
        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedWidth(80)
        self._save_btn.clicked.connect(self._save)

        # Font size +/- buttons
        self._font_minus_btn = QPushButton("-")
        self._font_minus_btn.setFixedWidth(28)
        self._font_minus_btn.setToolTip("Decrease font size")
        self._font_minus_btn.clicked.connect(self._decrease_font)

        self._font_plus_btn = QPushButton("+")
        self._font_plus_btn.setFixedWidth(28)
        self._font_plus_btn.setToolTip("Increase font size")
        self._font_plus_btn.clicked.connect(self._increase_font)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888; padding-left: 10px;")

        # Bottom bar with save button, font controls, and status
        bottom_bar = QHBoxLayout()
        bottom_bar.addWidget(self._save_btn)
        bottom_bar.addWidget(self._font_minus_btn)
        bottom_bar.addWidget(self._font_plus_btn)
        bottom_bar.addWidget(self._status_label, stretch=1)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(model_bar)
        layout.addWidget(self.text_edit)
        layout.addLayout(bottom_bar)
        self.setLayout(layout)

    def set_font_size(self, size: int) -> None:
        """Set the editor font size, clamped to MIN_FONT_SIZE–MAX_FONT_SIZE.

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

        # Populate model combo from scene YAML (#120)
        self._sync_model_combo_from_yaml(block)

    def is_dirty(self) -> bool:
        """Return True if the editor content differs from the loaded text."""
        return self.text_edit.toPlainText() != self._original_text

    def _save(self) -> None:
        """Save the edited YAML block back to project.yaml.

        Detects conflicts between the model combo selector and the YAML
        text.  When they disagree, shows a warning dialog with three
        options: save as YAML (trust text), save with selector (trust
        combo), or cancel (#124).
        """
        if not self._yaml_path or not self._scene_number:
            return

        # Detect model combo vs YAML text conflict (#124)
        combo_text = self._model_combo.currentText().strip()
        yaml_model = self._get_current_yaml_model()

        # Normalise: empty string and None are both "no model"
        combo_val = combo_text or None
        yaml_val = yaml_model or None

        if combo_val != yaml_val:
            result = QMessageBox.warning(
                self,
                "Model Override Conflict",
                f'The model selector shows "{combo_val or "(none)"}" '
                f'but the YAML text has "{yaml_val or "(none)"}".\n\n'
                "Which version should be saved?",
                QMessageBox.Save | QMessageBox.Apply | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if result == QMessageBox.Save:
                # Trust the YAML text — leave it as-is
                pass
            elif result == QMessageBox.Apply:
                # Trust the combo — sync combo into YAML
                if combo_text:
                    self._on_model_selected(combo_text)
                else:
                    self._on_clear_model()
            else:
                # Cancel — abort save
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

    # --- Model override bar (#120) ---

    def _sync_model_combo_from_yaml(self, block: str) -> None:
        """Parse model/provider from a scene YAML block and update the combo.

        Looks for ``model:`` or ``provider: {backend, model}`` keys
        in the scene block. Updates the combo without triggering
        re-injection into the YAML text.
        """
        self._model_combo.blockSignals(True)
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError:
            self._model_combo.setCurrentText("")
            self._backend_label.setText("")
            self._model_combo.blockSignals(False)
            return

        # Scene block parses as a list with one dict (YAML list item)
        if isinstance(parsed, list) and len(parsed) == 1:
            parsed = parsed[0]
        if not isinstance(parsed, dict):
            self._model_combo.setCurrentText("")
            self._backend_label.setText("")
            self._model_combo.blockSignals(False)
            return

        model_id = None
        # Check for provider: block first (has both backend and model)
        provider = parsed.get("provider")
        if isinstance(provider, dict) and provider.get("model"):
            model_id = str(provider["model"])
        # Then check for bare model: key
        elif parsed.get("model"):
            model_id = str(parsed["model"])

        if model_id:
            self._model_combo.setCurrentText(model_id)
            self._update_backend_label(model_id)
        else:
            self._model_combo.setCurrentText("")
            self._backend_label.setText("")
        self._model_combo.blockSignals(False)

    def _get_current_yaml_model(self) -> str | None:
        """Extract the current model ID from the YAML text, or None."""
        text = self.text_edit.toPlainText()
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            return None
        if isinstance(parsed, list) and len(parsed) == 1:
            parsed = parsed[0]
        if not isinstance(parsed, dict):
            return None
        provider = parsed.get("provider")
        if isinstance(provider, dict) and provider.get("model"):
            return str(provider["model"])
        if parsed.get("model"):
            return str(parsed["model"])
        return None

    def _update_backend_label(self, model_text: str) -> None:
        """Update the backend label to show the provider for the given model."""
        all_models = get_all_models()
        backend = all_models.get(model_text, "")
        self._backend_label.setText(backend)

    def _on_model_text_changed(self, text: str) -> None:
        """Handle model combo text change — update backend label."""
        self._update_backend_label(text)

    def _on_model_selected(self, model_id: str) -> None:
        """Inject or update the model override in the YAML text.

        Sets ``model: <id>`` on the scene. If the model belongs to
        a different backend than the scene's current provider, also
        sets ``provider: {backend: X, model: Y}``.
        """
        text = self.text_edit.toPlainText()
        lines = text.split("\n")

        # Detect indentation from first content line
        indent = "    "
        for line in lines:
            stripped = line.lstrip()
            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith("-")
            ):
                indent = line[: len(line) - len(stripped)]
                break

        # Remove existing model: and provider: lines
        lines = self._remove_model_lines(lines)

        # Find insertion point (after type: or duration: or title:, before prompt:)
        insert_idx = len(lines)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("prompt:"):
                insert_idx = i
                break

        # Determine if we need a full provider: block
        all_models = get_all_models()
        backend = all_models.get(model_id, "")

        if backend:
            # Insert provider: block with backend and model
            provider_lines = [
                f"{indent}provider:",
                f"{indent}  backend: {backend}",
                f'{indent}  model: "{model_id}"',
            ]
            for j, pl in enumerate(provider_lines):
                lines.insert(insert_idx + j, pl)
        else:
            # Unknown backend — just insert model:
            lines.insert(insert_idx, f'{indent}model: "{model_id}"')

        self.text_edit.setPlainText("\n".join(lines))
        self._model_combo.blockSignals(True)
        self._model_combo.setCurrentText(model_id)
        self._model_combo.blockSignals(False)
        self._update_backend_label(model_id)

    def _on_clear_model(self) -> None:
        """Remove model/provider override from the YAML text."""
        text = self.text_edit.toPlainText()
        lines = text.split("\n")
        lines = self._remove_model_lines(lines)
        self.text_edit.setPlainText("\n".join(lines))
        self._model_combo.blockSignals(True)
        self._model_combo.setCurrentText("")
        self._model_combo.blockSignals(False)
        self._backend_label.setText("")

    @staticmethod
    def _remove_model_lines(lines: list[str]) -> list[str]:
        """Remove model: and provider: block lines from a scene YAML block.

        Handles both ``model: X`` and multi-line ``provider:`` blocks
        with indented ``backend:`` and ``model:`` children.
        """
        result: list[str] = []
        skip_provider_block = False
        provider_indent: int | None = None

        for line in lines:
            stripped = line.strip()

            # Track provider: block and skip its children
            if skip_provider_block:
                if stripped and not stripped.startswith("#"):
                    line_indent = len(line) - len(line.lstrip())
                    if provider_indent is not None and line_indent > provider_indent:
                        continue  # Skip child of provider: block
                skip_provider_block = False
                provider_indent = None

            if re.match(r"^\s+provider:\s*$", line):
                # Multi-line provider: block
                skip_provider_block = True
                provider_indent = len(line) - len(line.lstrip())
                continue

            if re.match(r"^\s+provider:\s+\S", line):
                # Inline provider: {backend: ..., model: ...}
                continue

            if re.match(r"^\s+model:\s+", line):
                continue

            result.append(line)

        return result
