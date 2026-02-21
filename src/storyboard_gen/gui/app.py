# ABOUTME: Main application window for storyboard-gen GUI.
# ABOUTME: Orchestrates scene list, preview panel, console, and generation controls.

import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QToolBar,
    QWidget,
)

from storyboard_gen import __version__
from storyboard_gen.config import ConfigError, load_project
from storyboard_gen.gui.console_panel import ConsolePanel, QtLogHandler
from storyboard_gen.gui.generate_dialog import GenerateDialog
from storyboard_gen.gui.generate_worker import GenerateWorker
from storyboard_gen.gui.output_dialog import OutputDialog
from storyboard_gen.gui.preview_panel import PreviewPanel
from storyboard_gen.gui.scene_list import SceneListWidget, get_scene_status
from storyboard_gen.gui.yaml_viewer import YamlViewer
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
        self._gen_total: int = 0
        self._gen_done: int = 0

        self._setup_widgets()
        self._setup_toolbar()
        self._setup_logging()
        self._update_actions_enabled()

    def _setup_widgets(self) -> None:
        """Create and layout the main widgets."""
        self.scene_list = SceneListWidget()
        self.preview = PreviewPanel()
        self.console = ConsolePanel()
        self.yaml_viewer = YamlViewer()

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
        """Create the toolbar with generation, output, and refresh actions."""
        self.toolbar = QToolBar("Main")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self._action_open = self.toolbar.addAction("Open Project")
        self._action_open.triggered.connect(self._on_open_project)

        self._action_refresh = self.toolbar.addAction("Refresh")
        self._action_refresh.triggered.connect(self._on_refresh)

        self.toolbar.addSeparator()

        self._action_generate = self.toolbar.addAction("Generate")
        self._action_generate.triggered.connect(self._on_generate)

        self._action_stop = self.toolbar.addAction("Stop")
        self._action_stop.triggered.connect(self._on_stop)

        self.toolbar.addSeparator()

        self._action_output = self.toolbar.addAction("Output")
        self._action_output.triggered.connect(self._on_output)

        self.toolbar.addSeparator()

        self._action_yaml = self.toolbar.addAction("View YAML")
        self._action_yaml.triggered.connect(self._on_view_yaml)

        # Progress spinner and label in the toolbar
        spacer = QWidget()
        spacer.setSizePolicy(
            spacer.sizePolicy().horizontalPolicy(),
            spacer.sizePolicy().verticalPolicy(),
        )
        spacer.setMinimumWidth(20)
        self.toolbar.addWidget(spacer)

        self._spinner = QProgressBar()
        self._spinner.setRange(0, 0)  # Indeterminate (busy spinner)
        self._spinner.setFixedWidth(120)
        self._spinner.setFixedHeight(16)
        self._spinner.setTextVisible(False)
        self._spinner.setVisible(False)
        self.toolbar.addWidget(self._spinner)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet("color: #888; padding-left: 10px;")
        self.toolbar.addWidget(self._progress_label)

    def _setup_logging(self) -> None:
        """Attach a Qt log handler to route log messages to the console."""
        self._log_handler = QtLogHandler()
        self._log_handler.log_signal.message.connect(self.console.append_message)

        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_handler)

    def _show_error(self, message: str) -> None:
        """Show an error to the user via a message box and the console.

        Args:
            message: The error message to display.
        """
        self.console.append_message(f"Error: {message}")
        QMessageBox.critical(self, "Error", message)

    def _update_actions_enabled(self) -> None:
        """Enable/disable toolbar actions based on current state."""
        has_project = self._project is not None
        is_generating = self._worker is not None and self._worker.isRunning()

        self._action_generate.setEnabled(has_project and not is_generating)
        self._action_stop.setEnabled(is_generating)
        self._action_output.setEnabled(has_project and not is_generating)
        self._action_refresh.setEnabled(has_project)
        self._action_yaml.setEnabled(has_project)

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
            self._show_error(str(exc))
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

    def _on_refresh(self) -> None:
        """Reload the current project from disk."""
        if self._project_dir:
            self.open_project(self._project_dir)

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
                if path.exists():
                    self.preview.load_image(path)
                else:
                    self.preview.clear_image()
            else:
                path = self._output_dir / "clips" / f"scene_{scene_num}.mp4"
                if path.exists():
                    self.preview.play_clip(path)
                else:
                    self.preview.clear_image()
        else:
            self.preview.clear_image()

    # ----- Generation -----

    def _on_generate(self) -> None:
        """Open the Generate dialog and start generation."""
        if not self._project:
            return

        selected = self.scene_list.get_selected_scenes()
        dialog = GenerateDialog(
            self._project, selected_scenes=selected or None, parent=self
        )
        if dialog.exec():
            scenes = dialog.get_selected_scenes()
            self._start_generation(scenes)

    def _on_stop(self) -> None:
        """Request the current generation to stop."""
        if self._worker:
            self._worker.request_stop()
            self.console.append_message("Stop requested — finishing current scene...")

    def _start_generation(self, scenes: list[Scene]) -> None:
        """Start background generation for the given scenes."""
        if not scenes or not self._project:
            return

        self._gen_total = len(scenes)
        self._gen_done = 0
        self._progress_label.setText(f"0 / {self._gen_total}")
        self._spinner.setVisible(True)

        self.console.append_message(f"Generating {self._gen_total} scene(s)...")
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
        self._progress_label.setText(
            f"{self._gen_done} / {self._gen_total} — scene {scene.number}"
        )

    def _on_scene_gen_finished(self, scene: Scene) -> None:
        """Handle scene generation finished."""
        self._gen_done += 1
        self.console.append_message(f"Finished scene {scene.number}: {scene.title}")
        self._progress_label.setText(f"{self._gen_done} / {self._gen_total}")
        self.scene_list.refresh_status()
        self._refresh_preview_if_selected(scene)

    def _refresh_preview_if_selected(self, scene: Scene) -> None:
        """Refresh the preview panel if the given scene is currently selected."""
        selected = self.scene_list.get_selected_scene()
        if selected and selected.number == scene.number:
            self._on_scene_selected(scene)

    def _on_gen_error(self, message: str) -> None:
        """Handle generation error."""
        self._gen_done += 1
        self._show_error(message)
        self._progress_label.setText(f"{self._gen_done} / {self._gen_total}")

    def _on_gen_all_finished(self) -> None:
        """Handle all generation complete."""
        self.console.append_message("Generation complete.")
        self._progress_label.setText("")
        self._spinner.setVisible(False)
        self._worker = None
        self._update_actions_enabled()
        self.scene_list.refresh_status()

    # ----- Output (Assemble / Kdenlive) -----

    def _on_output(self) -> None:
        """Open the Output dialog and dispatch to assemble or kdenlive."""
        if not self._project:
            return

        default_title = self._project.title.replace(" ", "_").lower()
        dialog = OutputDialog(default_title=default_title, parent=self)
        if dialog.exec():
            options = dialog.get_options()
            if options["mode"] == "kdenlive":
                self._run_kdenlive(options)
            else:
                self._run_assemble(options)

    def _run_assemble(self, options: dict | None = None) -> None:
        """Run assembly in the main thread (fast operation).

        Args:
            options: Output dialog options (preview, audio, output).
        """
        if not self._project or not self._output_dir:
            return

        from storyboard_gen.assemble import assemble
        from storyboard_gen.ken_burns import apply_ken_burns

        if options is None:
            options = {"preview": False, "audio": None, "output": "assembled.mp4"}

        self.console.append_message("Assembling...")

        try:
            for scene in self._project.get_stills():
                scene_num = format_scene_number(scene.number)
                image_path = self._output_dir / "stills" / f"scene_{scene_num}.png"
                if not image_path.exists():
                    self._show_error(f"Missing still for scene {scene.number}")
                    return
                apply_ken_burns(
                    image_path, scene, self._project.aspect_ratio, self._output_dir
                )

            audio_path = None
            if not options.get("preview"):
                if options.get("audio"):
                    audio_path = options["audio"]
                elif self._project.audio:
                    audio_path = self._project.audio
                    if not audio_path.exists():
                        self.console.append_message(
                            f"Warning: Audio not found: {audio_path}"
                        )
                        audio_path = None

            output_filename = options.get("output", "assembled.mp4")

            assemble(
                self._project,
                self._output_dir,
                output_filename,
                audio_path=audio_path,
            )
            self.console.append_message("Assembly complete.")
        except (RuntimeError, OSError) as exc:
            self._show_error(f"Assembly failed: {exc}")

    def _run_kdenlive(self, options: dict) -> None:
        """Export a Kdenlive project file.

        Args:
            options: Output dialog options (preview, audio, output).
        """
        if not self._project or not self._output_dir:
            return

        from storyboard_gen.kdenlive import generate_kdenlive

        self.console.append_message("Exporting Kdenlive project...")

        try:
            audio_path = None
            if not options.get("preview"):
                if options.get("audio"):
                    audio_path = options["audio"]
                elif self._project.audio:
                    audio_path = self._project.audio
                    if not audio_path.exists():
                        self.console.append_message(
                            f"Warning: Audio not found: {audio_path}"
                        )
                        audio_path = None

            output_filename = options.get("output", f"{self._project.title}.kdenlive")

            output_path = generate_kdenlive(
                self._project,
                self._output_dir,
                output_filename=output_filename,
                audio_path=audio_path,
            )
            self.console.append_message(f"Kdenlive export complete: {output_path}")
        except (RuntimeError, OSError) as exc:
            self._show_error(f"Kdenlive export failed: {exc}")

    # ----- YAML viewer -----

    def _on_view_yaml(self) -> None:
        """Show the project.yaml in the YAML viewer."""
        if not self._project_dir:
            return

        yaml_path = self._project_dir / "project.yaml"
        self.yaml_viewer.load_file(yaml_path)
        self.yaml_viewer.setWindowTitle(f"project.yaml — {self._project_dir.name}")
        self.yaml_viewer.resize(700, 600)
        self.yaml_viewer.show()
        self.yaml_viewer.raise_()


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
