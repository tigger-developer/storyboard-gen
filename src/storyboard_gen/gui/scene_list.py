# ABOUTME: Scene list widget for storyboard-gen GUI.
# ABOUTME: Displays scenes with status indicators, inline action buttons, and emits selection signals.

from pathlib import Path

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyboard_gen.gui.archive_dialog import list_scene_archives
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


class SceneItemWidget(QWidget):
    """Custom widget for a scene list item with inline action buttons.

    Shows scene info (status, number, type, title) alongside
    Generate/Regenerate and Archive buttons.
    """

    generate_clicked = Signal(object)
    archive_clicked = Signal(object)
    stop_clicked = Signal(object)

    def __init__(
        self,
        scene: Scene,
        output_dir: Path,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._scene = scene
        self._output_dir = output_dir
        self._state = "idle"

        status = get_scene_status(scene, output_dir)
        indicator = "[OK]" if status == "generated" else "[--]"
        type_label = "S" if scene.scene_type == "still" else "C"

        # Scene info label
        self._label = QLabel(
            f"{indicator} {scene.number:>3} [{type_label}] {scene.title}"
        )

        # Per-scene spinner (indeterminate, hidden by default)
        self._spinner = QProgressBar()
        self._spinner.setRange(0, 0)
        self._spinner.setFixedWidth(60)
        self._spinner.setFixedHeight(14)
        self._spinner.setTextVisible(False)
        self._spinner.setVisible(False)

        # Generate / Regenerate button
        gen_text = "Regenerate" if status == "generated" else "Generate"
        self._gen_btn = QPushButton(gen_text)
        self._gen_btn.setFixedWidth(90)
        self._gen_btn.setToolTip(
            "Regenerate this scene" if status == "generated" else "Generate this scene"
        )
        self._gen_btn.clicked.connect(self._on_gen_btn_clicked)

        # Archive button
        has_archives = len(list_scene_archives(scene, output_dir)) > 0
        self._archive_btn = QPushButton("Archive")
        self._archive_btn.setFixedWidth(70)
        self._archive_btn.setToolTip("Browse archived versions")
        self._archive_btn.setEnabled(has_archives)
        self._archive_btn.clicked.connect(
            lambda: self.archive_clicked.emit(self._scene)
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._label, stretch=1)
        layout.addWidget(self._spinner)
        layout.addWidget(self._gen_btn)
        layout.addWidget(self._archive_btn)
        self.setLayout(layout)

    def _on_gen_btn_clicked(self) -> None:
        """Handle generate button click based on current state."""
        if self._state == "generating":
            self.stop_clicked.emit(self._scene)
        else:
            self.generate_clicked.emit(self._scene)

    def set_state(self, state: str) -> None:
        """Set the widget's generation state.

        Args:
            state: "idle" or "generating".
        """
        self._state = state
        if state == "idle":
            self._spinner.setVisible(False)
            status = get_scene_status(self._scene, self._output_dir)
            gen_text = "Regenerate" if status == "generated" else "Generate"
            self._gen_btn.setText(gen_text)
            self._gen_btn.setEnabled(True)
            has_archives = len(list_scene_archives(self._scene, self._output_dir)) > 0
            self._archive_btn.setEnabled(has_archives)
        elif state == "generating":
            self._spinner.setVisible(True)
            self._gen_btn.setText("Stop")
            self._gen_btn.setEnabled(True)
            self._archive_btn.setEnabled(False)

    def refresh(self) -> None:
        """Update the widget state from current output and archive status."""
        status = get_scene_status(self._scene, self._output_dir)
        indicator = "[OK]" if status == "generated" else "[--]"
        type_label = "S" if self._scene.scene_type == "still" else "C"

        self._label.setText(
            f"{indicator} {self._scene.number:>3} [{type_label}] {self._scene.title}"
        )

        # Only update button text/state if idle (generating/queued managed by set_state)
        if self._state == "idle":
            gen_text = "Regenerate" if status == "generated" else "Generate"
            self._gen_btn.setText(gen_text)
            self._gen_btn.setToolTip(
                "Regenerate this scene"
                if status == "generated"
                else "Generate this scene"
            )
            has_archives = len(list_scene_archives(self._scene, self._output_dir)) > 0
            self._archive_btn.setEnabled(has_archives)


class SceneListWidget(QWidget):
    """Scrollable list of scenes with status indicators and action buttons.

    Emits ``scene_selected(Scene)`` when the user clicks a scene.
    Emits ``generate_requested(Scene)`` when a scene's Generate button is clicked.
    Emits ``archive_requested(Scene)`` when a scene's Archive button is clicked.
    Emits ``stop_requested(Scene)`` when a scene's Stop button is clicked.
    """

    scene_selected = Signal(object)
    generate_requested = Signal(object)
    archive_requested = Signal(object)
    stop_requested = Signal(object)

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
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 36))
            self.list_widget.addItem(item)

            item_widget = SceneItemWidget(scene, output_dir)
            item_widget.generate_clicked.connect(self.generate_requested.emit)
            item_widget.archive_clicked.connect(self.archive_requested.emit)
            item_widget.stop_clicked.connect(self.stop_requested.emit)
            self.list_widget.setItemWidget(item, item_widget)

    def refresh_status(self) -> None:
        """Refresh status indicators and button states for all scenes."""
        if not self._output_dir:
            return
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item_widget = self.list_widget.itemWidget(item)
            if isinstance(item_widget, SceneItemWidget):
                item_widget.refresh()

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

    def set_scene_state(self, number: str, state: str) -> None:
        """Set generation state for a single scene.

        Args:
            number: The scene number string.
            state: "idle" or "generating".
        """
        for i in range(self.list_widget.count()):
            item_widget = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(item_widget, SceneItemWidget):
                if str(self._scenes[i].number) == str(number):
                    item_widget.set_state(state)
                    break

    def clear_generation_state(self) -> None:
        """Restore all scene items to idle state."""
        for i in range(self.list_widget.count()):
            item_widget = self.list_widget.itemWidget(self.list_widget.item(i))
            if isinstance(item_widget, SceneItemWidget):
                item_widget.set_state("idle")

    def _on_row_changed(self, row: int) -> None:
        """Handle row selection change."""
        if 0 <= row < len(self._scenes):
            self.scene_selected.emit(self._scenes[row])
