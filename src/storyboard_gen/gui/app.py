# ABOUTME: Main application window for storyboard-gen GUI.
# ABOUTME: Orchestrates scene list, preview panel, console, and generation controls.

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QSplitter,
    QToolBar,
    QWidget,
)

from storyboard_gen import __version__
from storyboard_gen.config import ConfigError, load_project
from storyboard_gen.gui.console_panel import ConsolePanel, QtLogHandler
from storyboard_gen.gui.generate_worker import GenerateWorker
from storyboard_gen.gui.preview_panel import PreviewPanel
from storyboard_gen.gui.scene_list import SceneListWidget, get_scene_status
from storyboard_gen.models import Project, Scene, format_scene_number

logger = logging.getLogger(__name__)

APP_TITLE = "storyboard-gen"


class MainWindow(QMainWindow):
    """Main application window for storyboard-gen GUI."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)

        self._project: Project | None = None
        self._project_dir: Path | None = None
        self._output_dir: Path | None = None
        self._worker: GenerateWorker | None = None

        self._setup_widgets()
        self._setup_toolbar()
        self._setup_logging()
        self._update_actions_enabled()

    def _setup_widgets(self) -> None:
        """Create and layout the main widgets."""
        self.scene_list = SceneListWidget()
        self.preview = PreviewPanel()
        self.console = ConsolePanel()

        # Scene list + preview side by side
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.scene_list)
        top_splitter.addWidget(self.preview)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 3)

        # Top panel + console stacked vertically
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.console)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)

        self.setCentralWidget(main_splitter)

        # Connect scene selection to preview
        self.scene_list.scene_selected.connect(self._on_scene_selected)

    def _setup_toolbar(self) -> None:
        """Create the toolbar with generation and assembly actions."""
        self.toolbar = QToolBar("Main")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self._action_open = self.toolbar.addAction("Open Project")
        self._action_open.triggered.connect(self._on_open_project)

        self.toolbar.addSeparator()

        self._action_gen_scene = self.toolbar.addAction("Generate Scene")
        self._action_gen_scene.triggered.connect(self._on_generate_scene)

        self._action_all_stills = self.toolbar.addAction("All Stills")
        self._action_all_stills.triggered.connect(self._on_generate_all_stills)

        self._action_all_clips = self.toolbar.addAction("All Clips")
        self._action_all_clips.triggered.connect(self._on_generate_all_clips)

        self._action_gen_all = self.toolbar.addAction("Generate All")
        self._action_gen_all.triggered.connect(self._on_generate_all)

        self.toolbar.addSeparator()

        self._action_assemble = self.toolbar.addAction("Assemble")
        self._action_assemble.triggered.connect(self._on_assemble)

        self._action_preview = self.toolbar.addAction("Preview")
        self._action_preview.triggered.connect(self._on_preview)

    def _setup_logging(self) -> None:
        """Attach a Qt log handler to route log messages to the console."""
        self._log_handler = QtLogHandler()
        self._log_handler.log_signal.message.connect(self.console.append_message)

        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_handler)

    def _update_actions_enabled(self) -> None:
        """Enable/disable toolbar actions based on current state."""
        has_project = self._project is not None
        is_generating = self._worker is not None and self._worker.isRunning()

        self._action_gen_scene.setEnabled(has_project and not is_generating)
        self._action_all_stills.setEnabled(has_project and not is_generating)
        self._action_all_clips.setEnabled(has_project and not is_generating)
        self._action_gen_all.setEnabled(has_project and not is_generating)
        self._action_assemble.setEnabled(has_project and not is_generating)
        self._action_preview.setEnabled(has_project and not is_generating)

    # ----- Project loading -----

    def open_project(self, project_dir: Path) -> None:
        """Load a project from the given directory.

        Args:
            project_dir: Directory containing project.yaml.
        """
        self.console.clear()
        self._project_dir = project_dir
        self._output_dir = project_dir / "output"

        try:
            self._project = load_project(project_dir)
        except ConfigError as exc:
            self.console.append_message(f"Error: {exc}")
            self._project = None
            self._update_actions_enabled()
            return

        self.setWindowTitle(f"{APP_TITLE} - {self._project.title}")
        self.scene_list.load_project(self._project, self._output_dir)
        self.console.append_message(
            f"Loaded project: {self._project.title} "
            f"({len(self._project.scenes)} scenes)"
        )
        self._update_actions_enabled()

    def _on_open_project(self) -> None:
        """Handle Open Project toolbar action."""
        directory = QFileDialog.getExistingDirectory(
            self, "Open Project Directory", str(Path.home())
        )
        if directory:
            self.open_project(Path(directory))

    # ----- Scene selection -----

    def _on_scene_selected(self, scene: Scene) -> None:
        """Handle scene selection — update the preview panel."""
        if not self._output_dir:
            return

        status = get_scene_status(scene, self._output_dir)
        if status == "generated":
            scene_num = format_scene_number(scene.number)
            if scene.scene_type == "still":
                path = self._output_dir / "stills" / f"scene_{scene_num}.png"
            else:
                # For clips, check if there's a thumbnail/still available
                path = self._output_dir / "clips" / f"scene_{scene_num}.mp4"
            if scene.scene_type == "still" and path.exists():
                self.preview.load_image(path)
            else:
                self.preview.clear_image()
        else:
            self.preview.clear_image()

    # ----- Generation -----

    def _start_generation(self, scenes: list[Scene]) -> None:
        """Start background generation for the given scenes."""
        if not scenes or not self._project:
            return

        self.console.append_message(f"Generating {len(scenes)} scene(s)...")
        self._worker = GenerateWorker(
            scenes=scenes,
            project=self._project,
            output_dir=self._output_dir,
            project_dir=self._project_dir,
        )
        self._worker.scene_started.connect(self._on_scene_gen_started)
        self._worker.scene_finished.connect(self._on_scene_gen_finished)
        self._worker.error.connect(self._on_gen_error)
        self._worker.all_finished.connect(self._on_gen_all_finished)
        self._update_actions_enabled()
        self._worker.start()

    def _on_scene_gen_started(self, scene: Scene) -> None:
        """Handle scene generation started."""
        self.console.append_message(
            f"Generating scene {scene.number}: {scene.title}..."
        )

    def _on_scene_gen_finished(self, scene: Scene) -> None:
        """Handle scene generation finished."""
        self.console.append_message(f"Finished scene {scene.number}: {scene.title}")
        self.scene_list.refresh_status()

    def _on_gen_error(self, message: str) -> None:
        """Handle generation error."""
        self.console.append_message(f"Error: {message}")

    def _on_gen_all_finished(self) -> None:
        """Handle all generation complete."""
        self.console.append_message("Generation complete.")
        self._worker = None
        self._update_actions_enabled()
        self.scene_list.refresh_status()

    def _on_generate_scene(self) -> None:
        """Generate the currently selected scene."""
        scene = self.scene_list.get_selected_scene()
        if scene:
            self._start_generation([scene])
        else:
            self.console.append_message("No scene selected.")

    def _on_generate_all_stills(self) -> None:
        """Generate all still scenes."""
        if self._project:
            self._start_generation(self._project.get_stills())

    def _on_generate_all_clips(self) -> None:
        """Generate all clip scenes."""
        if self._project:
            self._start_generation(self._project.get_clips())

    def _on_generate_all(self) -> None:
        """Generate all scenes."""
        if self._project:
            self._start_generation(list(self._project.scenes))

    # ----- Assembly -----

    def _on_assemble(self) -> None:
        """Assemble final video with audio."""
        self._run_assemble(preview=False)

    def _on_preview(self) -> None:
        """Assemble preview video without audio."""
        self._run_assemble(preview=True)

    def _run_assemble(self, preview: bool) -> None:
        """Run assembly in the main thread (fast operation).

        Args:
            preview: If True, skip audio muxing.
        """
        if not self._project or not self._output_dir:
            return

        from storyboard_gen.assemble import assemble
        from storyboard_gen.ken_burns import apply_ken_burns

        mode = "preview" if preview else "full"
        self.console.append_message(f"Assembling ({mode})...")

        try:
            for scene in self._project.get_stills():
                scene_num = format_scene_number(scene.number)
                image_path = self._output_dir / "stills" / f"scene_{scene_num}.png"
                if not image_path.exists():
                    self.console.append_message(
                        f"Error: Missing still for scene {scene.number}"
                    )
                    return
                apply_ken_burns(
                    image_path, scene, self._project.aspect_ratio, self._output_dir
                )

            audio_path = None
            if not preview and self._project.audio:
                audio_path = self._project.audio
                if not audio_path.exists():
                    self.console.append_message(
                        f"Warning: Audio not found: {audio_path}"
                    )
                    audio_path = None

            assemble(
                self._project,
                self._output_dir,
                "assembled.mp4",
                audio_path=audio_path,
            )
            self.console.append_message("Assembly complete.")
        except (RuntimeError, OSError) as exc:
            self.console.append_message(f"Error: Assembly failed: {exc}")


def run(project_dir: str | None = None) -> int:
    """Launch the storyboard-gen GUI application.

    Args:
        project_dir: Optional project directory to open on launch.

    Returns:
        Application exit code.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()

    if project_dir:
        window.open_project(Path(project_dir))

    return app.exec()
