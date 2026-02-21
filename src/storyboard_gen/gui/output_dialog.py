# ABOUTME: Dialog for choosing output mode (Assemble MP4 or Kdenlive export).
# ABOUTME: Provides preview mode, audio override, and output filename options.

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class OutputDialog(QDialog):
    """Dialog for selecting output mode and options.

    Modes: Assemble (MP4) or Kdenlive export (.kdenlive).
    Options: preview mode (no audio), audio file override, output filename.
    """

    def __init__(
        self,
        default_title: str = "assembled",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Output")
        self._audio_path: Path | None = None

        # Mode radio group
        mode_group = QGroupBox("Output mode")
        self._radio_assemble = QRadioButton("Assemble (MP4)")
        self._radio_kdenlive = QRadioButton("Kdenlive export")
        self._radio_assemble.setChecked(True)

        mode_layout = QVBoxLayout()
        mode_layout.addWidget(self._radio_assemble)
        mode_layout.addWidget(self._radio_kdenlive)
        mode_group.setLayout(mode_layout)

        # Update default filename when mode changes
        self._default_title = default_title
        self._radio_assemble.toggled.connect(self._update_default_filename)
        self._radio_kdenlive.toggled.connect(self._update_default_filename)

        # Options
        self._preview_check = QCheckBox("Preview mode (no audio)")

        # Audio override
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(QLabel("Audio override:"))
        self._audio_label = QLabel("(project default)")
        self._audio_label.setStyleSheet("color: #888;")
        audio_layout.addWidget(self._audio_label, 1)
        self._audio_browse = QPushButton("Browse...")
        self._audio_browse.clicked.connect(self._browse_audio)
        audio_layout.addWidget(self._audio_browse)

        # Output filename
        filename_layout = QHBoxLayout()
        filename_layout.addWidget(QLabel("Output filename:"))
        self._filename_edit = QLineEdit(f"{default_title}.mp4")
        filename_layout.addWidget(self._filename_edit, 1)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(mode_group)
        layout.addWidget(self._preview_check)
        layout.addLayout(audio_layout)
        layout.addLayout(filename_layout)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _update_default_filename(self) -> None:
        """Update the default filename when mode changes."""
        current = self._filename_edit.text()
        if self._radio_kdenlive.isChecked():
            if current.endswith(".mp4"):
                self._filename_edit.setText(current.rsplit(".mp4", 1)[0] + ".kdenlive")
        else:
            if current.endswith(".kdenlive"):
                self._filename_edit.setText(current.rsplit(".kdenlive", 1)[0] + ".mp4")

    def _browse_audio(self) -> None:
        """Open a file dialog to select an audio file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            "Audio Files (*.m4a *.mp3 *.wav *.aac *.ogg);;All Files (*)",
        )
        if path:
            self._audio_path = Path(path)
            self._audio_label.setText(Path(path).name)
            self._audio_label.setStyleSheet("")

    def get_options(self) -> dict:
        """Return the selected output options.

        Returns:
            Dict with keys: mode, preview, audio, output.
        """
        return {
            "mode": "kdenlive" if self._radio_kdenlive.isChecked() else "assemble",
            "preview": self._preview_check.isChecked(),
            "audio": self._audio_path,
            "output": self._filename_edit.text(),
        }
