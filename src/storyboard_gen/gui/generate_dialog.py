# ABOUTME: Dialog for selecting which scenes to generate.
# ABOUTME: Supports multi-scene selection from the scene list with cost estimates.

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from storyboard_gen.generate import resolve_provider_config
from storyboard_gen.models import Project, Scene
from storyboard_gen.pricing import estimate_scene_cost


class GenerateDialog(QDialog):
    """Dialog that lets the user choose which scenes to generate.

    Options: all stills, all clips, all scenes, or selected scene(s).
    Optionally displays cost estimates when a pricing_map is provided.
    """

    def __init__(
        self,
        project: Project,
        selected_scenes: list[Scene] | None = None,
        parent: QWidget | None = None,
        pricing_map: dict[str, dict] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Generate")
        self._project = project
        self._selected_scenes = selected_scenes or []
        self._pricing_map = pricing_map or {}

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

        # Dry-run checkbox
        self._dry_run_check = QCheckBox("Dry run (preview only, no API calls)")

        # Cost summary label
        self._cost_label = QLabel()
        self._cost_label.setStyleSheet("color: #888; margin-top: 6px;")

        # Connect radio buttons to update cost display
        self._radio_all.toggled.connect(self._update_cost)
        self._radio_stills.toggled.connect(self._update_cost)
        self._radio_clips.toggled.connect(self._update_cost)
        self._radio_selected.toggled.connect(self._update_cost)

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
        layout.addWidget(self._dry_run_check)
        layout.addWidget(self._cost_label)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self._update_cost()

    def _update_cost(self) -> None:
        """Recalculate and display the cost summary for the current selection."""
        if not self._pricing_map:
            self._cost_label.setText("")
            return

        scenes = self.get_selected_scenes()
        total = 0.0
        has_pricing = False

        for scene in scenes:
            provider_cfg = resolve_provider_config(
                scene, self._project, scene.scene_type
            )
            pricing = self._pricing_map.get(provider_cfg.model)
            cost = estimate_scene_cost(scene, pricing)
            if cost is not None:
                total += cost
                has_pricing = True

        if has_pricing:
            self._cost_label.setText(
                f"Estimated cost: ${total:.2f} ({len(scenes)} scene"
                f"{'s' if len(scenes) != 1 else ''})"
            )
        else:
            self._cost_label.setText("")

    def is_dry_run(self) -> bool:
        """Return True if the dry-run checkbox is checked."""
        return self._dry_run_check.isChecked()

    def get_selected_scenes(self) -> list[Scene]:
        """Return the list of scenes matching the user's selection."""
        if self._radio_stills.isChecked():
            return self._project.get_stills()
        if self._radio_clips.isChecked():
            return self._project.get_clips()
        if self._radio_selected.isChecked() and self._selected_scenes:
            return list(self._selected_scenes)
        return list(self._project.scenes)
