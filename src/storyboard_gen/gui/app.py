# ABOUTME: Main application window for storyboard-gen GUI.
# ABOUTME: Orchestrates scene list, preview panel, console, and generation controls.

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QToolBar,
    QToolButton,
    QWidget,
)

from storyboard_gen import __version__
from storyboard_gen.config import ConfigError, load_project
from storyboard_gen.gui.about_dialog import AboutDialog
from storyboard_gen.gui.console_panel import ConsolePanel, QtLogHandler
from storyboard_gen.gui.generate_dialog import GenerateDialog
from storyboard_gen.gui.generate_worker import GenerateWorker
from storyboard_gen.gui.archive_dialog import ArchiveDialog
from storyboard_gen.gui.output_dialog import OutputDialog
from storyboard_gen.gui.preview_panel import PreviewPanel
from storyboard_gen.gui.scene_list import SceneListWidget, get_scene_status
from storyboard_gen.pricing import fetch_price
from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor
from storyboard_gen.gui.settings import AppSettings
from storyboard_gen.gui.yaml_viewer import YamlViewer
from storyboard_gen.models import Project, Scene, format_scene_number

logger = logging.getLogger(__name__)

APP_TITLE = "storyboard-gen"
_DEFAULT_WINDOW_WIDTH = 1400
_DEFAULT_WINDOW_HEIGHT = 800
_TOOLBAR_BUTTON_SIZE = 36
_TOOLBAR_FONT_SIZE_PT = 18


def _shortcut_modifier_label() -> str:
    """Return the platform-appropriate modifier key label for tooltips."""
    return "Cmd" if sys.platform == "darwin" else "Ctrl"


class MainWindow(QMainWindow):
    """Main application window for storyboard-gen GUI."""

    def __init__(self, parent: QWidget | None = None, verbose: bool = False):
        super().__init__(parent)
        self.setWindowTitle(APP_TITLE)
        self.resize(_DEFAULT_WINDOW_WIDTH, _DEFAULT_WINDOW_HEIGHT)

        self._project: Project | None = None
        self._project_dir: Path | None = None
        self._output_dir: Path | None = None
        self._workers: dict[str, GenerateWorker] = {}
        self._settings = AppSettings()
        self._pricing_map: dict[str, dict] = {}

        self._setup_widgets()
        self._setup_toolbar()
        self._setup_shortcuts()
        self._setup_logging(verbose=verbose)
        self._update_actions_enabled()

    def _setup_widgets(self) -> None:
        """Create and layout the main widgets."""
        self.scene_list = SceneListWidget()
        self.preview = PreviewPanel()
        self.yaml_editor = SceneYamlEditor()
        self.console = ConsolePanel()
        self.yaml_viewer = YamlViewer()
        self.yaml_viewer.project_saved.connect(self._on_project_settings_saved)

        # Wire YAML editor signals
        self.yaml_editor.scene_modified.connect(self._on_scene_yaml_modified)
        self.yaml_editor.font_size_changed.connect(self._on_font_size_changed)

        # Apply stored font size
        self.yaml_editor.set_font_size(self._settings.editor_font_size)

        # Scene list + preview + YAML editor side by side
        self._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._content_splitter.addWidget(self.scene_list)
        self._content_splitter.addWidget(self.preview)
        self._content_splitter.addWidget(self.yaml_editor)
        self._content_splitter.setStretchFactor(0, 1)
        self._content_splitter.setStretchFactor(1, 2)
        self._content_splitter.setStretchFactor(2, 2)

        # YAML editor hidden by default (toggleable like console)
        self.yaml_editor.setVisible(False)

        # Allow the content area to shrink so the console can grow (#119)
        self._content_splitter.setMinimumHeight(100)

        # Content + console stacked vertically (console hidden by default)
        self._main_splitter = QSplitter(Qt.Orientation.Vertical)
        self._main_splitter.addWidget(self._content_splitter)
        self._main_splitter.addWidget(self.console)
        self._main_splitter.setStretchFactor(0, 3)
        self._main_splitter.setStretchFactor(1, 1)
        self.console.setVisible(False)

        self.setCentralWidget(self._main_splitter)

        # Connect scene selection to preview
        self.scene_list.scene_selected.connect(self._on_scene_selected)

        # Connect per-scene action buttons
        self.scene_list.generate_requested.connect(self._on_generate_scene)
        self.scene_list.archive_requested.connect(self._on_archive_scene)
        self.scene_list.stop_requested.connect(self._on_stop_scene)

    @staticmethod
    def _make_toolbar_button(emoji: str, tooltip: str, callback) -> QToolButton:
        """Create a square toolbar button with an emoji icon and tooltip.

        Args:
            emoji: Emoji character to display as the button label.
            tooltip: Tooltip text describing the action.
            callback: Slot to connect to the clicked signal.
        """
        btn = QToolButton()
        btn.setText(emoji)
        btn.setToolTip(tooltip)
        btn.setFixedSize(_TOOLBAR_BUTTON_SIZE, _TOOLBAR_BUTTON_SIZE)
        btn.setStyleSheet(f"font-size: {_TOOLBAR_FONT_SIZE_PT}pt;")
        btn.clicked.connect(callback)
        return btn

    def _setup_toolbar(self) -> None:
        """Create the toolbar with icon buttons, progress spinner, and label."""
        mod = _shortcut_modifier_label()
        self.toolbar = QToolBar("Main")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self._btn_open = self._make_toolbar_button(
            "📂", f"Open Project ({mod}+O)", self._on_open_project
        )
        self.toolbar.addWidget(self._btn_open)

        self._btn_new = self._make_toolbar_button(
            "➕", f"New Project ({mod}+N)", self._on_new_project
        )
        self.toolbar.addWidget(self._btn_new)

        self._btn_refresh = self._make_toolbar_button(
            "🔄", f"Refresh ({mod}+R)", self._on_refresh
        )
        self.toolbar.addWidget(self._btn_refresh)

        self.toolbar.addSeparator()

        self._btn_generate = self._make_toolbar_button(
            "🚀", f"Generate ({mod}+G)", self._on_generate
        )
        self.toolbar.addWidget(self._btn_generate)

        self._btn_stop = self._make_toolbar_button(
            "⏹", f"Stop ({mod}+Shift+C)", self._on_stop_all
        )
        self.toolbar.addWidget(self._btn_stop)

        self.toolbar.addSeparator()

        self._btn_output = self._make_toolbar_button(
            "🎞", f"Output ({mod}+Shift+O)", self._on_output
        )
        self.toolbar.addWidget(self._btn_output)

        self.toolbar.addSeparator()

        self._btn_yaml_viewer = self._make_toolbar_button(
            "📄", f"View YAML ({mod}+Y / {mod}+,)", self._on_view_yaml
        )
        self.toolbar.addWidget(self._btn_yaml_viewer)

        self._btn_yaml_editor = self._make_toolbar_button(
            "✏️", f"Edit YAML ({mod}+Shift+Y)", self._on_toggle_yaml
        )
        self.toolbar.addWidget(self._btn_yaml_editor)

        self._btn_env = self._make_toolbar_button(
            "🔑", f"Provider Config ({mod}+E)", self._on_edit_env
        )
        self.toolbar.addWidget(self._btn_env)

        self._btn_console = self._make_toolbar_button(
            "🖥", f"Console ({mod}+L)", self._on_toggle_console
        )
        self.toolbar.addWidget(self._btn_console)

        self._btn_about = self._make_toolbar_button(
            "ℹ️", f"About ({mod}+I)", self._on_about
        )
        self.toolbar.addWidget(self._btn_about)

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

    def _setup_shortcuts(self) -> None:
        """Create global keyboard shortcuts.

        Qt maps Ctrl to Cmd on macOS automatically, so Ctrl+X in code
        becomes Cmd+X on macOS and Ctrl+X on Linux/Windows.
        """
        # Scene navigation: Cmd+[ (previous) and Cmd+] (next)
        self._shortcut_prev = QShortcut(QKeySequence("Ctrl+["), self)
        self._shortcut_prev.activated.connect(self.scene_list.select_previous)
        self._shortcut_next = QShortcut(QKeySequence("Ctrl+]"), self)
        self._shortcut_next.activated.connect(self.scene_list.select_next)

        # Toolbar action shortcuts (Ctrl maps to Cmd on macOS)
        self._shortcut_open = QShortcut(QKeySequence("Ctrl+O"), self)
        self._shortcut_open.activated.connect(self._on_open_project)
        self._shortcut_new = QShortcut(QKeySequence("Ctrl+N"), self)
        self._shortcut_new.activated.connect(self._on_new_project)
        self._shortcut_refresh = QShortcut(QKeySequence("Ctrl+R"), self)
        self._shortcut_refresh.activated.connect(self._on_refresh)
        self._shortcut_generate = QShortcut(QKeySequence("Ctrl+G"), self)
        self._shortcut_generate.activated.connect(self._on_generate)
        self._shortcut_yaml = QShortcut(QKeySequence("Ctrl+Y"), self)
        self._shortcut_yaml.activated.connect(self._on_view_yaml)
        self._shortcut_console = QShortcut(QKeySequence("Ctrl+L"), self)
        self._shortcut_console.activated.connect(self._on_toggle_console)
        self._shortcut_about = QShortcut(QKeySequence("Ctrl+I"), self)
        self._shortcut_about.activated.connect(self._on_about)

        # Save shortcut for scene YAML editor
        self._shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self._shortcut_save.activated.connect(self._on_save_yaml)

        # Shift shortcuts
        self._shortcut_stop = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self._shortcut_stop.activated.connect(self._on_stop_all)
        self._shortcut_output = QShortcut(QKeySequence("Ctrl+Shift+O"), self)
        self._shortcut_output.activated.connect(self._on_output)
        self._shortcut_edit_yaml = QShortcut(QKeySequence("Ctrl+Shift+Y"), self)
        self._shortcut_edit_yaml.activated.connect(self._on_toggle_yaml)
        self._shortcut_edit_yaml2 = QShortcut(QKeySequence("Ctrl+,"), self)
        self._shortcut_edit_yaml2.activated.connect(self._on_view_yaml)
        self._shortcut_env = QShortcut(QKeySequence("Ctrl+E"), self)
        self._shortcut_env.activated.connect(self._on_edit_env)

    def _setup_logging(self, verbose: bool = False) -> None:
        """Attach a Qt log handler to route log messages to the console.

        Args:
            verbose: If True, also log to stderr for debugging.
        """
        self._log_handler = QtLogHandler()
        self._log_handler.log_signal.message.connect(self.console.append_message)

        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_handler)

        if verbose:
            stderr_handler = logging.StreamHandler(sys.stderr)
            stderr_handler.setLevel(logging.DEBUG)
            stderr_handler.setFormatter(
                logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s")
            )
            stderr_handler._verbose_marker = True  # noqa: SLF001 — marker for test cleanup
            root_logger.addHandler(stderr_handler)
            root_logger.setLevel(logging.DEBUG)

    def _show_error(self, message: str) -> None:
        """Show an error to the user via a message box and the console.

        Args:
            message: The error message to display.
        """
        self.console.append_message(f"Error: {message}")
        QMessageBox.critical(self, "Error", message)

    def _update_actions_enabled(self) -> None:
        """Enable/disable toolbar buttons based on current state."""
        has_project = self._project is not None
        is_generating = len(self._workers) > 0

        self._btn_generate.setEnabled(has_project)
        self._btn_stop.setEnabled(is_generating)
        self._btn_output.setEnabled(has_project and not is_generating)
        self._btn_refresh.setEnabled(has_project)
        self._btn_yaml_viewer.setEnabled(has_project)
        self._btn_env.setEnabled(has_project)

    def _update_progress(self) -> None:
        """Update toolbar spinner and progress label based on active workers."""
        count = len(self._workers)
        if count > 0:
            self._spinner.setVisible(True)
            self._progress_label.setText(f"Generating {count} scene(s)...")
        else:
            self._spinner.setVisible(False)
            self._progress_label.setText("")

    # ----- Project loading -----

    def open_project(self, project_dir: Path) -> None:
        """Load a project from the given directory.

        Args:
            project_dir: Directory containing project.yaml.
        """
        self.console.clear()
        self._project_dir = project_dir
        self._output_dir = project_dir / "output"

        # Load .env so provider credentials are available (same as CLI)
        load_dotenv(project_dir / ".env", override=True)

        try:
            self._project = load_project(project_dir)
        except ConfigError as exc:
            self._show_error(str(exc))
            self._project = None
            self._update_actions_enabled()
            return

        self.setWindowTitle(f"{APP_TITLE} - {self._project.title}")

        # Fetch pricing for unique FAL models in the project
        self._pricing_map = self._fetch_project_pricing(self._project)

        self.scene_list.load_project(
            self._project, self._output_dir, pricing_map=self._pricing_map
        )
        # Ensure archive buttons reflect current disk state (#99)
        self.scene_list.refresh_status()
        self.console.append_message(
            f"Loaded project: {self._project.title} "
            f"({len(self._project.scenes)} scenes)"
        )
        self._update_actions_enabled()

        # Persist session state
        self._settings.last_project = str(project_dir)
        self._settings.last_directory = str(project_dir.parent)

    @staticmethod
    def _fetch_project_pricing(project: Project) -> dict[str, dict]:
        """Fetch pricing for all unique models in the project.

        Returns a dict mapping model endpoint IDs to pricing dicts.
        Models without pricing are silently skipped.
        """
        from storyboard_gen.generate import resolve_provider_config

        # Collect unique models with their pricing overrides
        model_overrides: dict[str, dict | None] = {}
        for scene in project.scenes:
            cfg = resolve_provider_config(scene, project, scene.scene_type)
            if cfg.model not in model_overrides:
                model_overrides[cfg.model] = cfg.pricing

        pricing_map: dict[str, dict] = {}
        for model, override in model_overrides.items():
            pricing = fetch_price(model, pricing_override=override)
            if pricing is not None:
                pricing_map[model] = pricing
        return pricing_map

    def _on_open_project(self) -> None:
        """Handle Open Project toolbar action."""
        start_dir = self._settings.last_directory
        if not start_dir or not Path(start_dir).exists():
            start_dir = str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self, "Open Project Directory", start_dir
        )
        if directory:
            self._settings.last_directory = str(Path(directory).parent)
            self.open_project(Path(directory))

    def _on_new_project(self) -> None:
        """Handle New Project toolbar action.

        Prompts for a parent directory and project name, scaffolds
        the project, and opens it.
        """
        from storyboard_gen.cli import init_project

        parent = QFileDialog.getExistingDirectory(
            self, "Select Location for New Project", str(Path.home())
        )
        if not parent:
            return

        name, ok = QInputDialog.getText(self, "New Project", "Enter project name:")
        if not ok or not name.strip():
            return

        target = Path(parent) / name.strip()

        try:
            init_project(target)
        except FileExistsError:
            self._show_error(f"A project already exists at {target}")
            return
        except OSError as exc:
            self._show_error(f"Failed to create project: {exc}")
            return

        self.open_project(target)

    def _on_refresh(self) -> None:
        """Reload the current project from disk."""
        if self._project_dir:
            self.open_project(self._project_dir)

    # ----- Scene selection -----

    def _on_scene_selected(self, scene: Scene) -> None:
        """Handle scene selection — update the preview panel and YAML editor."""
        if not self._output_dir:
            return

        # Clear green fresh indicator when scene is viewed
        self.scene_list.clear_scene_fresh(str(scene.number))

        # Check for unsaved YAML changes before switching
        if self.yaml_editor.is_dirty():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved YAML changes. Discard them?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return

        # Update preview panel
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

        # Update YAML editor
        if self._project_dir:
            yaml_path = self._project_dir / "project.yaml"
            self.yaml_editor.load_scene(str(scene.number), yaml_path)

    # ----- Generation -----

    def _on_generate(self) -> None:
        """Open the Generate dialog and start generation or dry run."""
        if not self._project:
            return

        selected = self.scene_list.get_selected_scenes()
        dialog = GenerateDialog(
            self._project,
            selected_scenes=selected or None,
            parent=self,
            pricing_map=self._pricing_map,
        )
        if dialog.exec():
            scenes = dialog.get_selected_scenes()
            if dialog.is_dry_run():
                self._run_dry_run(scenes)
            else:
                self._start_generation(scenes)

    def _run_dry_run(self, scenes: list[Scene]) -> None:
        """Print a dry-run summary of what would be generated.

        Shows provider, model, prompt, and cost for each scene
        without making any API calls.
        """
        if not self._project:
            return

        from storyboard_gen.generate import (
            check_field_warnings,
            resolve_provider_config,
        )
        from storyboard_gen.pricing import (
            estimate_scene_cost,
            fetch_price,
            format_cost_line,
        )

        self.console.setVisible(True)
        self.console.append_message("--- Dry Run ---")

        total_cost = 0.0
        has_any_pricing = False

        for scene in scenes:
            provider_cfg = resolve_provider_config(
                scene, self._project, scene.scene_type
            )
            prompt = self._project.build_prompt(scene)
            refs = self._project.get_reference_images(scene)

            lines = [f"Scene {scene.number}: {scene.title}"]
            lines.append(f"  Type:       {scene.scene_type}")
            lines.append(f"  Duration:   {scene.duration:g}s")
            if scene.camera:
                lines.append(f"  Camera:     {scene.camera}")
            if scene.ken_burns:
                lines.append(f"  Ken Burns:  {scene.ken_burns}")
            lines.append(f"  Provider:   {provider_cfg.backend} / {provider_cfg.model}")
            if provider_cfg.options:
                lines.append(f"  Options:    {provider_cfg.options}")
            if refs:
                lines.append("  References:")
                for ref in refs:
                    status = "ok" if ref.exists() else "MISSING"
                    lines.append(f"    [{status}] {ref}")

            pricing = fetch_price(
                provider_cfg.model, pricing_override=provider_cfg.pricing
            )
            lines.append(f"  {format_cost_line(scene, pricing)}")
            scene_cost = estimate_scene_cost(scene, pricing)
            if scene_cost is not None:
                total_cost += scene_cost
                has_any_pricing = True

            lines.append("  Prompt:")
            lines.append(f"    {prompt}")

            warns = check_field_warnings(scene, self._project, provider_cfg)
            for w in warns:
                lines.append(f"  {w}")

            self.console.append_message("\n".join(lines))

        if has_any_pricing:
            self.console.append_message(f"Estimated total cost: ${total_cost:.2f}")

        self.console.append_message("--- End Dry Run ---")

    def _on_stop_scene(self, scene: Scene) -> None:
        """Stop generation for a specific scene."""
        self._stop_scene_generation(scene)

    def _on_stop_all(self) -> None:
        """Stop all running generation workers."""
        self._stop_all_generation()

    def _start_generation(self, scenes: list[Scene]) -> None:
        """Start concurrent background generation for the given scenes.

        Checks for unsupported YAML fields and shows a warning dialog
        with Proceed/Cancel if any are found (#118).
        """
        if not scenes or not self._project:
            return

        from storyboard_gen.generate import (
            check_field_warnings,
            resolve_provider_config,
        )

        all_warnings: list[str] = []
        for scene in scenes:
            provider_cfg = resolve_provider_config(
                scene, self._project, scene.scene_type
            )
            warns = check_field_warnings(scene, self._project, provider_cfg)
            all_warnings.extend(warns)

        if all_warnings:
            detail = "\n".join(all_warnings)
            reply = QMessageBox.warning(
                self,
                "Field Warnings",
                "Some YAML fields are not supported by the selected models:\n\n"
                + detail
                + "\n\nProceed anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        for scene in scenes:
            self._start_scene_generation(scene)

    def _reload_project_for_generation(self) -> Project | None:
        """Reload project.yaml and .env from disk before generation.

        Ensures the worker always uses the latest YAML and credentials,
        even when edited externally (#75, #76).

        Returns:
            Fresh Project, or None on error.
        """
        load_dotenv(self._project_dir / ".env", override=True)
        try:
            return load_project(self._project_dir)
        except ConfigError as exc:
            self._show_error(f"Failed to reload project: {exc}")
            return None

    def _start_scene_generation(self, scene: Scene) -> None:
        """Start background generation for a single scene.

        Creates a per-scene worker thread. If the scene is already
        generating, the request is ignored. Reloads project.yaml and
        .env from disk before creating the worker (#75, #76).
        """
        if not self._project or not self._project_dir:
            return

        scene_key = str(scene.number)

        # Skip if this scene is already generating
        if scene_key in self._workers:
            return

        # Reload project and .env from disk to pick up external changes (#75, #76)
        fresh_project = self._reload_project_for_generation()
        if fresh_project is None:
            return

        # Find the matching scene in the fresh project
        fresh_scene = next(
            (s for s in fresh_project.scenes if str(s.number) == scene_key),
            None,
        )
        if fresh_scene is None:
            self._show_error(f"Scene {scene_key} not found in current project.yaml")
            return

        self.console.append_message(
            f"Generating scene {fresh_scene.number}: {fresh_scene.title}..."
        )

        worker = GenerateWorker(
            scene=fresh_scene,
            project=fresh_project,
            output_dir=self._output_dir,
            project_dir=self._project_dir,
        )
        worker.scene_started.connect(self._on_scene_gen_started)
        worker.scene_finished.connect(self._on_scene_gen_finished)
        worker.stopped.connect(self._on_scene_stopped)
        worker.error.connect(lambda msg, s=scene: self._on_gen_error(s, msg))
        worker.finished.connect(lambda key=scene_key: self._cleanup_worker(key))
        self._workers[scene_key] = worker
        self.scene_list.set_scene_state(scene_key, "generating")
        self._update_actions_enabled()
        self._update_progress()
        worker.start()

    def _stop_scene_generation(self, scene: Scene) -> None:
        """Stop generation for a specific scene.

        Args:
            scene: The scene to stop generating.
        """
        scene_key = str(scene.number)
        worker = self._workers.get(scene_key)
        if worker:
            worker.request_stop()
            self.console.append_message(f"Stop requested for scene {scene.number}...")

    def _stop_all_generation(self) -> None:
        """Stop all running generation workers."""
        for scene_key, worker in self._workers.items():
            worker.request_stop()
        if self._workers:
            self.console.append_message("Stop all requested...")

    def _on_scene_gen_started(self, scene: Scene) -> None:
        """Handle scene generation started signal from worker."""
        self.scene_list.set_scene_state(str(scene.number), "generating")

    def _on_scene_gen_finished(self, scene: Scene) -> None:
        """Handle scene generation finished.

        Worker cleanup is deferred to ``_cleanup_worker`` via the
        QThread ``finished`` signal — avoids GC destroying the thread
        while the OS thread is still unwinding.
        """
        scene_key = str(scene.number)
        self.console.append_message(f"Finished scene {scene.number}: {scene.title}")
        self.scene_list.set_scene_state(scene_key, "idle")
        self.scene_list.refresh_status()
        self.scene_list.set_scene_fresh(scene_key)
        self._refresh_preview_if_selected(scene)
        self._update_actions_enabled()
        self._update_progress()

    def _refresh_preview_if_selected(self, scene: Scene) -> None:
        """Refresh the preview panel if the given scene is currently selected."""
        selected = self.scene_list.get_selected_scene()
        if selected and selected.number == scene.number:
            self._on_scene_selected(scene)

    def _on_scene_stopped(self, scene: Scene) -> None:
        """Handle worker stopped signal — clean up state after cooperative stop.

        Worker removal deferred to ``_cleanup_worker`` via ``finished``.
        """
        scene_key = str(scene.number)
        self.console.append_message(f"Stopped scene {scene.number}: {scene.title}")
        self.scene_list.set_scene_state(scene_key, "idle")
        self.scene_list.refresh_status()
        self._update_actions_enabled()
        self._update_progress()

    def _on_gen_error(self, scene: Scene, message: str) -> None:
        """Handle generation error for a specific scene.

        Shows error via _show_error (console + QMessageBox) so the user
        always sees failures, even with the console collapsed (#122).

        Worker removal deferred to ``_cleanup_worker`` via ``finished``.
        """
        scene_key = str(scene.number)
        self._show_error(message)
        self.scene_list.set_scene_state(scene_key, "idle")
        self._update_actions_enabled()
        self._update_progress()

    def _cleanup_worker(self, scene_key: str) -> None:
        """Remove a finished worker from the tracking dict.

        Connected to QThread.finished — fires after the OS thread has
        fully terminated, so it's safe to drop the last Python reference.
        """
        self._workers.pop(scene_key, None)
        self._update_actions_enabled()
        self._update_progress()

    def closeEvent(self, event) -> None:
        """Save window layout and wait for workers before closing."""
        # Persist window geometry and splitter states (#119)
        self._settings.window_geometry = bytes(self.saveGeometry())
        self._settings.main_splitter_state = bytes(self._main_splitter.saveState())
        self._settings.content_splitter_state = bytes(
            self._content_splitter.saveState()
        )
        self._settings.console_visible = not self.console.isHidden()
        self._settings.yaml_editor_visible = not self.yaml_editor.isHidden()

        if self._workers:
            self._stop_all_generation()
            for worker in list(self._workers.values()):
                worker.wait(5000)
        super().closeEvent(event)

    def _on_generate_scene(self, scene: Scene) -> None:
        """Handle per-scene Generate/Regenerate button click."""
        if not self._project:
            return
        self._start_scene_generation(scene)

    def _on_archive_scene(self, scene: Scene) -> None:
        """Handle per-scene Archive button click."""
        if not self._output_dir:
            return

        dialog = ArchiveDialog(scene, self._output_dir, parent=self)
        dialog.exec()

        if dialog.restored:
            self.scene_list.refresh_status()
            self._refresh_preview_if_selected(scene)
            self.console.append_message(
                f"Restored archived version for scene {scene.number}"
            )

    # ----- YAML editor toggle -----

    def _on_toggle_yaml(self) -> None:
        """Toggle the YAML editor pane visibility."""
        currently_hidden = self.yaml_editor.isHidden()
        self.yaml_editor.setVisible(currently_hidden)

    def _on_save_yaml(self) -> None:
        """Save the scene YAML editor if it is visible and has unsaved changes."""
        if not self.yaml_editor.isHidden() and self.yaml_editor.is_dirty():
            self.yaml_editor._save()

    def _on_font_size_changed(self, size: int) -> None:
        """Persist YAML editor font size to settings."""
        self._settings.editor_font_size = size

    # ----- Console toggle -----

    def _on_toggle_console(self) -> None:
        """Toggle the console panel visibility."""
        currently_hidden = self.console.isHidden()
        self.console.setVisible(currently_hidden)

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
            subtitles_path = None
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

                if self._project.subtitles:
                    subtitles_path = self._project.subtitles
                    if not subtitles_path.exists():
                        self.console.append_message(
                            f"Warning: Subtitles not found: {subtitles_path}"
                        )
                        subtitles_path = None

            output_filename = options.get("output", f"{self._project.title}.kdenlive")

            output_path = generate_kdenlive(
                self._project,
                self._output_dir,
                output_filename=output_filename,
                audio_path=audio_path,
                subtitles_path=subtitles_path,
            )
            self.console.append_message(f"Kdenlive export complete: {output_path}")
        except (RuntimeError, OSError) as exc:
            self._show_error(f"Kdenlive export failed: {exc}")

    # ----- About dialog -----

    def _on_edit_env(self) -> None:
        """Open the .env editor dialog for provider credentials."""
        if not self._project_dir:
            return

        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = self._project_dir / ".env"
        dialog = EnvEditorDialog(env_path=env_path, parent=self)
        if dialog.exec():
            # Reload .env so credentials take effect immediately
            load_dotenv(env_path, override=True)
            self.console.append_message("Provider configuration saved.")

    def _on_about(self) -> None:
        """Show the About dialog."""
        dialog = AboutDialog(parent=self)
        dialog.exec()

    # ----- Session restore -----

    def restore_session(self) -> None:
        """Restore session state from persistent settings.

        Restores window geometry, splitter positions, panel visibility,
        and reopens the last project if the directory still exists.
        Called after the window is shown.
        """
        # Restore window layout (#119)
        geom = self._settings.window_geometry
        if geom is not None:
            from PySide6.QtCore import QByteArray

            self.restoreGeometry(QByteArray(geom))
        main_state = self._settings.main_splitter_state
        if main_state is not None:
            from PySide6.QtCore import QByteArray

            self._main_splitter.restoreState(QByteArray(main_state))
        content_state = self._settings.content_splitter_state
        if content_state is not None:
            from PySide6.QtCore import QByteArray

            self._content_splitter.restoreState(QByteArray(content_state))

        # Restore panel visibility
        if self._settings.console_visible:
            self.console.setVisible(True)
        if self._settings.yaml_editor_visible:
            self.yaml_editor.setVisible(True)

        last_project = self._settings.last_project
        if last_project:
            project_path = Path(last_project)
            if project_path.exists() and (project_path / "project.yaml").exists():
                self.open_project(project_path)

    # ----- YAML editor -----

    def _on_scene_yaml_modified(self) -> None:
        """Reload the project after a scene YAML edit is saved."""
        if self._project_dir:
            self.open_project(self._project_dir)

    # ----- YAML viewer -----

    def _on_project_settings_saved(self) -> None:
        """Reload the project after settings are saved via the YAML viewer form."""
        if self._project_dir:
            self.open_project(self._project_dir)

    def _on_view_yaml(self) -> None:
        """Show the project.yaml in the YAML viewer with settings form."""
        if not self._project_dir:
            return

        self.yaml_viewer.load_project(self._project_dir)
        self.yaml_viewer.setWindowTitle(f"project.yaml — {self._project_dir.name}")
        self.yaml_viewer.resize(1100, 700)
        self.yaml_viewer.show()
        self.yaml_viewer.raise_()


def _install_excepthook() -> None:
    """Install a global exception hook to log unhandled exceptions.

    Qt slots swallow Python exceptions silently. This hook ensures
    they are logged with full stack traces before re-raising.
    """
    _original = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        _original(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def run(project_dir: str | None = None, verbose: bool = False) -> int:
    """Launch the storyboard-gen GUI application.

    Args:
        project_dir: Optional project directory to open on launch.
        verbose: If True, log to stderr for debugging.

    Returns:
        Application exit code.
    """
    _install_excepthook()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(__version__)

    window = MainWindow(verbose=verbose)
    window.show()

    if project_dir:
        window.open_project(Path(project_dir))
    else:
        window.restore_session()

    return app.exec()
