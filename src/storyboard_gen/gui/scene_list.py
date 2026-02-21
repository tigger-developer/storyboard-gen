# ABOUTME: Scene list widget for storyboard-gen GUI.
# ABOUTME: Displays scenes with status indicators and emits selection signals.

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storyboard_gen.models import Project, Scene, format_scene_number


def get_scene_status(scene: Scene, output_dir: Path) -> str:
    """Determine whether a scene's output file exists.

    Args:
        scene: The scene to check.
        output_dir: The project's output directory.

    Returns:
        "generated" if the output file exists, "pending" otherwise.
    """
    scene_num = format_scene_number(scene.number)
    if scene.scene_type == "still":
        path = output_dir / "stills" / f"scene_{scene_num}.png"
    else:
        path = output_dir / "clips" / f"scene_{scene_num}.mp4"
    if path.exists():
        return "generated"
    return "pending"


class SceneListWidget(QWidget):
    """Scrollable list of scenes with status indicators.

    Emits ``scene_selected(Scene)`` when the user clicks a scene.
    """

    scene_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list_widget.currentRowChanged.connect(self._on_row_changed)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

        self._scenes: list[Scene] = []
        self._output_dir: Path | None = None

    def load_project(self, project: Project, output_dir: Path) -> None:
        """Populate the list from a project's scenes.

        Args:
            project: The loaded project.
            output_dir: The project's output directory for status checks.
        """
        self.list_widget.clear()
        self._scenes = list(project.scenes)
        self._output_dir = output_dir

        for scene in self._scenes:
            status = get_scene_status(scene, output_dir)
            indicator = "[OK]" if status == "generated" else "[--]"
            type_label = "S" if scene.scene_type == "still" else "C"
            text = f"{indicator} {scene.number:>3} [{type_label}] {scene.title}"
            item = QListWidgetItem(text)
            self.list_widget.addItem(item)

    def refresh_status(self) -> None:
        """Refresh status indicators for all scenes."""
        if not self._output_dir:
            return
        for i, scene in enumerate(self._scenes):
            status = get_scene_status(scene, self._output_dir)
            indicator = "[OK]" if status == "generated" else "[--]"
            type_label = "S" if scene.scene_type == "still" else "C"
            text = f"{indicator} {scene.number:>3} [{type_label}] {scene.title}"
            self.list_widget.item(i).setText(text)

    def get_selected_scene(self) -> Scene | None:
        """Return the currently selected scene, or None."""
        row = self.list_widget.currentRow()
        if 0 <= row < len(self._scenes):
            return self._scenes[row]
        return None

    def get_selected_scenes(self) -> list[Scene]:
        """Return all selected scenes in scene order."""
        rows = sorted(
            index.row() for index in self.list_widget.selectionModel().selectedRows()
        )
        return [self._scenes[row] for row in rows if 0 <= row < len(self._scenes)]

    def _on_row_changed(self, row: int) -> None:
        """Handle row selection change."""
        if 0 <= row < len(self._scenes):
            self.scene_selected.emit(self._scenes[row])
