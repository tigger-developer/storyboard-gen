# ABOUTME: Form-based project settings editor for storyboard-gen GUI.
# ABOUTME: Provides editable fields for title, providers, aspect ratio, etc. with Save/Revert.

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyboard_gen.gui.yaml_editor_helpers import (
    get_nested,
    load_yaml_roundtrip,
    save_yaml_roundtrip,
    update_nested,
)
from storyboard_gen.model_registry import (
    get_all_models,
    get_backends,
    get_models_for_backend,
)
from storyboard_gen.models import VALID_ASPECT_RATIOS

logger = logging.getLogger(__name__)


class ProjectSettingsForm(QWidget):
    """Form panel for editing project-level YAML fields.

    Provides dropdowns for provider backends/models, text fields for
    title and style_prefix, file pickers for audio/subtitles, and
    per-character description editing.

    Emits ``saved`` when changes are written to disk.
    """

    saved = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._project_dir: Path | None = None
        self._yaml_data: dict | None = None
        self._dirty = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the form layout."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)

        # --- Title ---
        self._title_edit = QLineEdit()
        self._title_edit.textChanged.connect(self._mark_dirty)
        title_group = QGroupBox("Project")
        title_form = QFormLayout()
        title_form.addRow("Title:", self._title_edit)

        # --- Aspect Ratio ---
        self._aspect_combo = QComboBox()
        self._aspect_combo.setEditable(True)
        for ratio in sorted(VALID_ASPECT_RATIOS):
            self._aspect_combo.addItem(ratio)
        self._aspect_combo.currentTextChanged.connect(self._mark_dirty)
        title_form.addRow("Aspect Ratio:", self._aspect_combo)

        # --- Style Prefix ---
        self._style_edit = QPlainTextEdit()
        self._style_edit.setMinimumHeight(100)
        self._style_edit.textChanged.connect(self._mark_dirty)
        title_form.addRow("Style Prefix:", self._style_edit)

        title_group.setLayout(title_form)
        form_layout.addWidget(title_group)

        # --- Still Provider ---
        still_group = QGroupBox("Still Provider")
        still_form = QFormLayout()

        self._still_backend = QComboBox()
        for b in get_backends():
            self._still_backend.addItem(b)
        self._still_backend.currentTextChanged.connect(self._on_still_backend_changed)
        still_form.addRow("Backend:", self._still_backend)

        self._still_model = QComboBox()
        self._still_model.setEditable(True)
        self._install_model_completer(self._still_model)
        self._still_model.currentTextChanged.connect(self._on_still_model_changed)
        still_form.addRow("Model:", self._still_model)

        still_group.setLayout(still_form)
        form_layout.addWidget(still_group)

        # --- Clip Provider ---
        clip_group = QGroupBox("Clip Provider")
        clip_form = QFormLayout()

        self._clip_backend = QComboBox()
        for b in get_backends():
            self._clip_backend.addItem(b)
        self._clip_backend.currentTextChanged.connect(self._on_clip_backend_changed)
        clip_form.addRow("Backend:", self._clip_backend)

        self._clip_model = QComboBox()
        self._clip_model.setEditable(True)
        self._install_model_completer(self._clip_model)
        self._clip_model.currentTextChanged.connect(self._on_clip_model_changed)
        clip_form.addRow("Model:", self._clip_model)

        clip_group.setLayout(clip_form)
        form_layout.addWidget(clip_group)

        # --- Audio / Subtitles ---
        media_group = QGroupBox("Media Files")
        media_form = QFormLayout()

        audio_row = QHBoxLayout()
        self._audio_edit = QLineEdit()
        self._audio_edit.textChanged.connect(self._mark_dirty)
        audio_browse = QPushButton("Browse...")
        audio_browse.clicked.connect(self._browse_audio)
        audio_row.addWidget(self._audio_edit)
        audio_row.addWidget(audio_browse)
        media_form.addRow("Audio:", audio_row)

        subs_row = QHBoxLayout()
        self._subs_edit = QLineEdit()
        self._subs_edit.textChanged.connect(self._mark_dirty)
        subs_browse = QPushButton("Browse...")
        subs_browse.clicked.connect(self._browse_subtitles)
        subs_row.addWidget(self._subs_edit)
        subs_row.addWidget(subs_browse)
        media_form.addRow("Subtitles:", subs_row)

        media_group.setLayout(media_form)
        form_layout.addWidget(media_group)

        # --- Characters ---
        self._chars_group = QGroupBox("Characters")
        self._chars_layout = QFormLayout()
        self._char_edits: dict[str, QPlainTextEdit] = {}
        self._chars_group.setLayout(self._chars_layout)
        form_layout.addWidget(self._chars_group)

        # --- Save / Revert buttons ---
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        self._revert_btn = QPushButton("Revert")
        self._revert_btn.setEnabled(False)
        self._revert_btn.clicked.connect(self._revert)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._revert_btn)
        form_layout.addLayout(btn_row)

        form_layout.addStretch()

        scroll.setWidget(form_container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_project(self, project_dir: Path) -> None:
        """Load project.yaml and populate form fields."""
        self._project_dir = project_dir
        yaml_path = project_dir / "project.yaml"
        if not yaml_path.exists():
            return
        self._yaml_data = load_yaml_roundtrip(yaml_path)
        self._populate_from_data()
        self._dirty = False
        self._save_btn.setEnabled(False)
        self._revert_btn.setEnabled(False)

    def _populate_from_data(self) -> None:
        """Fill form fields from loaded YAML data."""
        data = self._yaml_data
        if data is None:
            return

        # Block signals during population to avoid false dirty marks
        self._block_signals(True)

        self._title_edit.setText(str(data.get("title", "")))

        aspect = str(data.get("aspect_ratio", "16:9"))
        idx = self._aspect_combo.findText(aspect)
        if idx >= 0:
            self._aspect_combo.setCurrentIndex(idx)
        else:
            self._aspect_combo.setCurrentText(aspect)

        self._style_edit.setPlainText(str(data.get("style_prefix", "")))

        # Still provider
        still_backend = str(
            get_nested(data, ["providers", "still", "backend"], "google")
        )
        idx = self._still_backend.findText(still_backend)
        if idx >= 0:
            self._still_backend.setCurrentIndex(idx)
        self._update_model_combo(self._still_model, still_backend)
        still_model = str(get_nested(data, ["providers", "still", "model"], ""))
        self._still_model.setCurrentText(still_model)

        # Clip provider
        clip_backend = str(get_nested(data, ["providers", "clip", "backend"], "google"))
        idx = self._clip_backend.findText(clip_backend)
        if idx >= 0:
            self._clip_backend.setCurrentIndex(idx)
        self._update_model_combo(self._clip_model, clip_backend)
        clip_model = str(get_nested(data, ["providers", "clip", "model"], ""))
        self._clip_model.setCurrentText(clip_model)

        # Audio / Subtitles
        self._audio_edit.setText(str(data.get("audio", "")))
        self._subs_edit.setText(str(data.get("subtitles", "")))

        # Characters
        self._populate_characters(data.get("characters", {}))

        self._block_signals(False)

    def _populate_characters(self, chars: dict) -> None:
        """Build character description fields from YAML data."""
        # Clear existing
        for edit in self._char_edits.values():
            edit.deleteLater()
        self._char_edits.clear()

        # Remove all rows from the form layout
        while self._chars_layout.count():
            item = self._chars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not isinstance(chars, dict):
            return

        for name, char_data in chars.items():
            desc = ""
            if isinstance(char_data, dict):
                desc = str(char_data.get("description", ""))
            edit = QPlainTextEdit()
            edit.setMaximumHeight(40)
            edit.setPlainText(desc)
            edit.textChanged.connect(self._mark_dirty)
            self._char_edits[name] = edit
            self._chars_layout.addRow(f"{name}:", edit)

    def _block_signals(self, block: bool) -> None:
        """Block or unblock signals on all editable widgets."""
        for widget in (
            self._title_edit,
            self._aspect_combo,
            self._style_edit,
            self._still_backend,
            self._still_model,
            self._clip_backend,
            self._clip_model,
            self._audio_edit,
            self._subs_edit,
        ):
            widget.blockSignals(block)
        for edit in self._char_edits.values():
            edit.blockSignals(block)

    def _mark_dirty(self) -> None:
        """Mark the form as having unsaved changes."""
        self._dirty = True
        self._save_btn.setEnabled(True)
        self._revert_btn.setEnabled(True)

    def is_dirty(self) -> bool:
        """Return True if the form has unsaved changes."""
        return self._dirty

    def _on_still_backend_changed(self, backend: str) -> None:
        """Update still model dropdown when backend changes."""
        self._update_model_combo(self._still_model, backend)
        self._mark_dirty()

    def _on_clip_backend_changed(self, backend: str) -> None:
        """Update clip model dropdown when backend changes."""
        self._update_model_combo(self._clip_model, backend)
        self._mark_dirty()

    def _update_model_combo(self, combo: QComboBox, backend: str) -> None:
        """Populate a model combobox for the given backend."""
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        for m in get_models_for_backend(backend):
            combo.addItem(m)
        # Restore previous text if it was a custom model
        combo.setCurrentText(current)
        combo.blockSignals(False)

    def _browse_audio(self) -> None:
        """Open file picker for audio file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            str(self._project_dir) if self._project_dir else "",
            "Audio Files (*.mp3 *.wav *.aac *.m4a *.ogg);;All Files (*)",
        )
        if path and self._project_dir:
            rel = Path(path).relative_to(self._project_dir)
            self._audio_edit.setText(str(rel))

    def _browse_subtitles(self) -> None:
        """Open file picker for subtitles file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Subtitles File",
            str(self._project_dir) if self._project_dir else "",
            "Subtitle Files (*.srt *.ass *.vtt);;All Files (*)",
        )
        if path and self._project_dir:
            rel = Path(path).relative_to(self._project_dir)
            self._subs_edit.setText(str(rel))

    def _save(self) -> None:
        """Write form values back to project.yaml using format-preserving YAML."""
        if not self._project_dir or not self._yaml_data:
            return

        data = self._yaml_data

        # Title
        data["title"] = self._title_edit.text()

        # Aspect ratio
        data["aspect_ratio"] = self._aspect_combo.currentText()

        # Style prefix
        style = self._style_edit.toPlainText().strip()
        if style:
            data["style_prefix"] = style
        else:
            data.pop("style_prefix", None)

        # Still provider
        update_nested(
            data, ["providers", "still", "backend"], self._still_backend.currentText()
        )
        update_nested(
            data, ["providers", "still", "model"], self._still_model.currentText()
        )
        # Remove options when backend/model changed
        if get_nested(data, ["providers", "still", "options"]):
            update_nested(data, ["providers", "still", "options"], None)

        # Clip provider
        update_nested(
            data, ["providers", "clip", "backend"], self._clip_backend.currentText()
        )
        update_nested(
            data, ["providers", "clip", "model"], self._clip_model.currentText()
        )
        if get_nested(data, ["providers", "clip", "options"]):
            update_nested(data, ["providers", "clip", "options"], None)

        # Audio / Subtitles
        audio = self._audio_edit.text().strip()
        if audio:
            data["audio"] = audio
        else:
            data.pop("audio", None)

        subs = self._subs_edit.text().strip()
        if subs:
            data["subtitles"] = subs
        else:
            data.pop("subtitles", None)

        # Characters (descriptions only, preserve references)
        chars = data.get("characters", {})
        for name, edit in self._char_edits.items():
            if name in chars and isinstance(chars[name], dict):
                chars[name]["description"] = edit.toPlainText().strip()

        yaml_path = self._project_dir / "project.yaml"
        save_yaml_roundtrip(data, yaml_path)

        self._dirty = False
        self._save_btn.setEnabled(False)
        self._revert_btn.setEnabled(False)
        self.saved.emit()
        logger.info("Project settings saved to %s", yaml_path)

    def _revert(self) -> None:
        """Reload form from disk, discarding unsaved changes."""
        if self._project_dir:
            self.load_project(self._project_dir)

    @staticmethod
    def _install_model_completer(combo: QComboBox) -> None:
        """Install a substring-matching completer with all models across all backends."""
        all_model_ids = sorted(get_all_models().keys())
        completer = QCompleter(all_model_ids)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        combo.setCompleter(completer)

    def _auto_switch_backend(self, model_text: str, backend_combo: QComboBox) -> None:
        """Switch backend combo to match the model's registered backend."""
        all_models = get_all_models()
        if model_text in all_models:
            expected_backend = all_models[model_text]
            if backend_combo.currentText() != expected_backend:
                backend_combo.blockSignals(True)
                idx = backend_combo.findText(expected_backend)
                if idx >= 0:
                    backend_combo.setCurrentIndex(idx)
                backend_combo.blockSignals(False)

    def _on_still_model_changed(self, text: str) -> None:
        """Handle still model text change: auto-switch backend and mark dirty."""
        self._auto_switch_backend(text, self._still_backend)
        self._mark_dirty()

    def _on_clip_model_changed(self, text: str) -> None:
        """Handle clip model text change: auto-switch backend and mark dirty."""
        self._auto_switch_backend(text, self._clip_backend)
        self._mark_dirty()
