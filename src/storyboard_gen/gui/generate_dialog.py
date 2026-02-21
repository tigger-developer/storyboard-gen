# ABOUTME: Dialog for selecting which scenes to generate.
# ABOUTME: Supports multi-scene selection from the scene list.

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from storyboard_gen.models import Project, Scene


class GenerateDialog(QDialog):
    """Dialog that lets the user choose which scenes to generate.

    Options: all stills, all clips, all scenes, or selected scene(s).
    """

    def __init__(
        self,
        project: Project,
        selected_scenes: list[Scene] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Generate")
        self._project = project
        self._selected_scenes = selected_scenes or []

        self._radio_all = QRadioButton("All scenes")
        self._radio_stills = QRadioButton("All stills")
        self._radio_clips = QRadioButton("All clips")
        self._radio_selected = QRadioButton("Selected scene(s)")

        self._radio_all.setChecked(True)

        # Enable and label the "Selected" radio based on selection count
        has_selection = len(self._selected_scenes) > 0
        self._radio_selected.setEnabled(has_selection)
        if len(self._selected_scenes) == 1:
            scene = self._selected_scenes[0]
            self._radio_selected.setText(f"Scene {scene.number}: {scene.title}")
        elif len(self._selected_scenes) > 1:
            self._radio_selected.setText(
                f"Selected: {len(self._selected_scenes)} scenes"
            )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self._radio_all)
        layout.addWidget(self._radio_stills)
        layout.addWidget(self._radio_clips)
        layout.addWidget(self._radio_selected)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_selected_scenes(self) -> list[Scene]:
        """Return the list of scenes matching the user's selection."""
        if self._radio_stills.isChecked():
            return self._project.get_stills()
        if self._radio_clips.isChecked():
            return self._project.get_clips()
        if self._radio_selected.isChecked() and self._selected_scenes:
            return list(self._selected_scenes)
        return list(self._project.scenes)
