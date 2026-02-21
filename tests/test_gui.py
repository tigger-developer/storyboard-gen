# ABOUTME: Tests for the storyboard-gen GUI module.
# ABOUTME: Covers scene status, log handler, widgets, and generate worker.

from unittest.mock import patch

import pytest
import yaml

PySide6 = pytest.importorskip("PySide6")

from storyboard_gen.models import Scene  # noqa: E402 — must follow importorskip


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PROJECT_YAML = {
    "title": "GUI Test Project",
    "aspect_ratio": "9:16",
    "style_prefix": "Watercolour illustration.",
    "characters": {
        "hero": {
            "description": "A young boy with red hair",
            "reference": ["references/hero.png"],
        },
    },
    "scenes": [
        {
            "number": 1,
            "title": "Opening shot",
            "type": "still",
            "duration": 5,
            "camera": "WIDE",
            "ken_burns": "zoom_in",
            "prompt": "A boy stands on a hill.",
            "characters": ["hero"],
        },
        {
            "number": 2,
            "title": "Action",
            "type": "clip",
            "duration": 6,
            "prompt": "The boy runs.",
        },
        {
            "number": 3,
            "title": "Closing",
            "type": "still",
            "duration": 4,
            "camera": "CLOSE",
            "ken_burns": "static",
            "prompt": "Close-up of the boy smiling.",
        },
    ],
}


@pytest.fixture
def gui_project_dir(tmp_path):
    """Create a temporary project directory for GUI tests."""
    yaml_path = tmp_path / "project.yaml"
    yaml_path.write_text(yaml.dump(SAMPLE_PROJECT_YAML))

    refs_dir = tmp_path / "references"
    refs_dir.mkdir()
    (refs_dir / "hero.png").write_bytes(b"fake-png")

    return tmp_path


@pytest.fixture
def gui_project_dir_with_output(gui_project_dir):
    """Project dir with some generated output files."""
    stills_dir = gui_project_dir / "output" / "stills"
    stills_dir.mkdir(parents=True)
    clips_dir = gui_project_dir / "output" / "clips"
    clips_dir.mkdir(parents=True)

    # Create a minimal valid PNG for scene 1 (1x1 red pixel)
    import struct
    import zlib

    def _make_png():
        """Create a minimal 1x1 red PNG."""
        signature = b"\x89PNG\r\n\x1a\n"

        def _chunk(chunk_type, data):
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        raw = zlib.compress(b"\x00\xff\x00\x00")
        return (
            signature
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", raw)
            + _chunk(b"IEND", b"")
        )

    (stills_dir / "scene_01.png").write_bytes(_make_png())
    # Scene 2 is a clip — create a dummy mp4
    (clips_dir / "scene_02.mp4").write_bytes(b"fake-mp4-data")
    # Scene 3 still is NOT generated (pending)

    return gui_project_dir


# ---------------------------------------------------------------------------
# Unit tests: scene_status
# ---------------------------------------------------------------------------


class TestSceneStatus:
    """Test scene output status resolution."""

    def test_still_scene_generated_returns_generated(self, gui_project_dir_with_output):
        """A still scene with output/stills/scene_01.png should be 'generated'."""
        from storyboard_gen.gui.scene_list import get_scene_status

        scene = Scene(
            number="1",
            title="Opening",
            scene_type="still",
            prompt="test",
            duration=5,
        )
        output_dir = gui_project_dir_with_output / "output"

        # Act
        status = get_scene_status(scene, output_dir)

        # Assert
        assert status == "generated"

    def test_clip_scene_generated_returns_generated(self, gui_project_dir_with_output):
        """A clip scene with output/clips/scene_02.mp4 should be 'generated'."""
        from storyboard_gen.gui.scene_list import get_scene_status

        scene = Scene(
            number="2",
            title="Action",
            scene_type="clip",
            prompt="test",
            duration=6,
        )
        output_dir = gui_project_dir_with_output / "output"

        # Act
        status = get_scene_status(scene, output_dir)

        # Assert
        assert status == "generated"

    def test_still_scene_pending_returns_pending(self, gui_project_dir_with_output):
        """A still scene without an output file should be 'pending'."""
        from storyboard_gen.gui.scene_list import get_scene_status

        scene = Scene(
            number="3",
            title="Closing",
            scene_type="still",
            prompt="test",
            duration=4,
        )
        output_dir = gui_project_dir_with_output / "output"

        # Act
        status = get_scene_status(scene, output_dir)

        # Assert
        assert status == "pending"

    def test_scene_with_no_output_dir_returns_pending(self, tmp_path):
        """When no output directory exists, status should be 'pending'."""
        from storyboard_gen.gui.scene_list import get_scene_status

        scene = Scene(
            number="1",
            title="Opening",
            scene_type="still",
            prompt="test",
            duration=5,
        )
        output_dir = tmp_path / "output"

        # Act
        status = get_scene_status(scene, output_dir)

        # Assert
        assert status == "pending"


# ---------------------------------------------------------------------------
# Unit tests: QtLogHandler
# ---------------------------------------------------------------------------


class TestQtLogHandler:
    """Test the custom logging handler that emits Qt signals."""

    def test_handler_emits_log_message(self, qtbot):
        """QtLogHandler should emit log_message signal with formatted text."""
        from storyboard_gen.gui.console_panel import QtLogHandler

        handler = QtLogHandler()
        received = []
        handler.log_signal.message.connect(received.append)

        # Act
        import logging

        logger = logging.getLogger("test_gui_handler")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.info("Test message")

        # Assert
        assert len(received) == 1
        assert "Test message" in received[0]

        # Cleanup
        logger.removeHandler(handler)

    def test_handler_includes_level_name(self, qtbot):
        """Log messages should include the level name."""
        from storyboard_gen.gui.console_panel import QtLogHandler

        handler = QtLogHandler()
        received = []
        handler.log_signal.message.connect(received.append)

        import logging

        logger = logging.getLogger("test_gui_handler_level")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.warning("Attention needed")

        assert len(received) == 1
        assert "WARNING" in received[0]

        logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# Integration tests: ConsolePanel
# ---------------------------------------------------------------------------


class TestConsolePanel:
    """Test the console panel widget."""

    def test_console_panel_creates(self, qtbot):
        """ConsolePanel should instantiate without error."""
        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)

        assert panel is not None

    def test_console_panel_append_message(self, qtbot):
        """ConsolePanel.append_message should add text to the display."""
        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)

        # Act
        panel.append_message("INFO: Hello world")

        # Assert
        assert "Hello world" in panel.text_edit.toPlainText()

    def test_console_panel_error_highlighted_red(self, qtbot):
        """Error messages should be rendered in red text."""
        from PySide6.QtGui import QColor

        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)

        # Act
        panel.append_message("Error: something broke")

        # Assert — check that the text colour is red
        cursor = panel.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.Right)
        fmt = cursor.charFormat()
        assert fmt.foreground().color() == QColor("#cc0000")

    def test_console_panel_warning_highlighted_amber(self, qtbot):
        """Warning messages should be rendered in amber text."""
        from PySide6.QtGui import QColor

        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)

        # Act
        panel.append_message("WARNING: heads up")

        # Assert
        cursor = panel.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.Right)
        fmt = cursor.charFormat()
        assert fmt.foreground().color() == QColor("#cc8800")

    def test_console_panel_clear(self, qtbot):
        """ConsolePanel.clear should empty the text display."""
        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)
        panel.append_message("Some message")

        # Act
        panel.clear()

        # Assert
        assert panel.text_edit.toPlainText() == ""


# ---------------------------------------------------------------------------
# Integration tests: PreviewPanel
# ---------------------------------------------------------------------------


class TestPreviewPanel:
    """Test the image preview panel widget."""

    def test_preview_panel_creates(self, qtbot):
        """PreviewPanel should instantiate without error."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        assert panel is not None

    def test_preview_panel_shows_placeholder_initially(self, qtbot):
        """PreviewPanel should show placeholder text when no image is loaded."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        # Assert — placeholder should be the current stacked widget
        assert panel._layout.currentWidget() is panel.placeholder_label

    def test_preview_panel_loads_image(self, qtbot, gui_project_dir_with_output):
        """PreviewPanel.load_image should display the image."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        image_path = gui_project_dir_with_output / "output" / "stills" / "scene_01.png"

        # Act
        panel.load_image(image_path)

        # Assert — image label should have a pixmap
        assert not panel.image_label.pixmap().isNull()

    def test_preview_panel_clear_image(self, qtbot, gui_project_dir_with_output):
        """PreviewPanel.clear_image should reset to placeholder."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        image_path = gui_project_dir_with_output / "output" / "stills" / "scene_01.png"
        panel.load_image(image_path)

        # Act
        panel.clear_image()

        # Assert — placeholder should be the current stacked widget
        assert panel._layout.currentWidget() is panel.placeholder_label


# ---------------------------------------------------------------------------
# Integration tests: SceneListWidget
# ---------------------------------------------------------------------------


class TestSceneListWidget:
    """Test the scene list widget."""

    def test_scene_list_creates(self, qtbot):
        """SceneListWidget should instantiate without error."""
        from storyboard_gen.gui.scene_list import SceneListWidget

        widget = SceneListWidget()
        qtbot.addWidget(widget)

        assert widget is not None

    def test_scene_list_populates_from_project(
        self, qtbot, gui_project_dir_with_output
    ):
        """SceneListWidget.load_project should populate items for each scene."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)

        # Act
        widget.load_project(project, output_dir)

        # Assert
        assert widget.list_widget.count() == 3

    def test_scene_list_emits_scene_selected(self, qtbot, gui_project_dir_with_output):
        """Clicking a scene should emit scene_selected signal."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Act — simulate selecting first item
        received = []
        widget.scene_selected.connect(received.append)
        widget.list_widget.setCurrentRow(0)

        # Assert
        assert len(received) == 1
        assert received[0].number == "1"

    def test_scene_list_shows_status_indicators(
        self, qtbot, gui_project_dir_with_output
    ):
        """Scene items should show status indicators based on output existence."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Assert — check item text contains status indicators
        item0_text = widget.list_widget.item(0).text()
        item2_text = widget.list_widget.item(2).text()

        # Scene 1 is generated, scene 3 is pending
        assert "[OK]" in item0_text or "✓" in item0_text
        assert "[--]" in item2_text or "✗" in item2_text


# ---------------------------------------------------------------------------
# Integration tests: GenerateWorker
# ---------------------------------------------------------------------------


class TestGenerateWorker:
    """Test the background generation worker."""

    def test_worker_emits_finished_on_success(self, qtbot, gui_project_dir):
        """Worker should emit finished signal after successful generation."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        scene = project.scenes[0]
        output_dir = gui_project_dir / "output"

        # Mock the generate function to avoid real API calls
        with patch("storyboard_gen.gui.generate_worker.generate_still") as mock_gen:
            mock_gen.return_value = output_dir / "stills" / "scene_01.png"

            worker = GenerateWorker(
                scenes=[scene],
                project=project,
                output_dir=output_dir,
                project_dir=gui_project_dir,
            )

            finished_scenes = []
            worker.scene_finished.connect(finished_scenes.append)

            all_done = []
            worker.all_finished.connect(lambda: all_done.append(True))

            # Act
            worker.run()

            # Assert
            assert len(finished_scenes) == 1
            assert finished_scenes[0] == scene
            assert len(all_done) == 1

    def test_worker_emits_error_on_failure(self, qtbot, gui_project_dir):
        """Worker should emit error signal if generation fails."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        scene = project.scenes[0]
        output_dir = gui_project_dir / "output"

        with patch("storyboard_gen.gui.generate_worker.generate_still") as mock_gen:
            mock_gen.side_effect = RuntimeError("API timeout")

            worker = GenerateWorker(
                scenes=[scene],
                project=project,
                output_dir=output_dir,
                project_dir=gui_project_dir,
            )

            errors = []
            worker.error.connect(errors.append)

            # Act
            worker.run()

            # Assert
            assert len(errors) == 1
            assert "API timeout" in errors[0]

    def test_worker_emits_error_on_import_error(self, qtbot, gui_project_dir):
        """Worker should emit error signal if provider SDK is missing."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        scene = project.scenes[0]
        output_dir = gui_project_dir / "output"

        with patch("storyboard_gen.gui.generate_worker.generate_still") as mock_gen:
            mock_gen.side_effect = ImportError(
                "fal-client is not installed. Run: pip install fal-client"
            )

            worker = GenerateWorker(
                scenes=[scene],
                project=project,
                output_dir=output_dir,
                project_dir=gui_project_dir,
            )

            errors = []
            worker.error.connect(errors.append)

            # Act
            worker.run()

            # Assert
            assert len(errors) == 1
            assert "fal-client" in errors[0]

    def test_worker_handles_mixed_scene_types(self, qtbot, gui_project_dir):
        """Worker should dispatch stills and clips to correct functions."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        output_dir = gui_project_dir / "output"

        with (
            patch("storyboard_gen.gui.generate_worker.generate_still") as mock_still,
            patch("storyboard_gen.gui.generate_worker.generate_clip") as mock_clip,
        ):
            mock_still.return_value = output_dir / "stills" / "scene_01.png"
            mock_clip.return_value = output_dir / "clips" / "scene_03.mp4"

            worker = GenerateWorker(
                scenes=project.scenes,
                project=project,
                output_dir=output_dir,
                project_dir=gui_project_dir,
            )

            # Act
            worker.run()

            # Assert
            assert mock_still.call_count == 2  # scenes 1 and 3 are stills
            assert mock_clip.call_count == 1  # scene 2 is a clip


# ---------------------------------------------------------------------------
# Integration tests: MainWindow
# ---------------------------------------------------------------------------


class TestMainWindow:
    """Test the main application window."""

    def test_main_window_creates(self, qtbot):
        """MainWindow should instantiate without error."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert window is not None
        assert window.windowTitle() == "storyboard-gen"

    def test_main_window_loads_project(self, qtbot, gui_project_dir_with_output):
        """MainWindow.open_project should populate the scene list."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Act
        window.open_project(gui_project_dir_with_output)

        # Assert
        assert window.scene_list.list_widget.count() == 3
        assert "GUI Test Project" in window.windowTitle()

    def test_main_window_shows_validation_error(self, qtbot, tmp_path):
        """MainWindow should show error in console for invalid project."""
        from storyboard_gen.gui.app import MainWindow

        # Create an invalid project.yaml (missing title)
        (tmp_path / "project.yaml").write_text(yaml.dump({"scenes": []}))

        window = MainWindow()
        qtbot.addWidget(window)

        # Act
        window.open_project(tmp_path)

        # Assert — console should contain error text
        console_text = window.console.text_edit.toPlainText()
        assert "error" in console_text.lower() or "Error" in console_text

    def test_main_window_toolbar_actions_exist(self, qtbot):
        """MainWindow should have toolbar actions for generation and output."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Assert — check toolbar actions
        action_texts = [a.text() for a in window.toolbar.actions() if a.text()]
        assert "Open Project" in action_texts
        assert "Refresh" in action_texts
        assert "Generate" in action_texts
        assert "Stop" in action_texts
        assert "Output" in action_texts
        assert "View YAML" in action_texts

    def test_main_window_stop_button_disabled_initially(self, qtbot):
        """Stop button should be disabled when not generating."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert not window._action_stop.isEnabled()

    def test_main_window_has_progress_label(self, qtbot):
        """MainWindow should have a progress label in the status bar."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_progress_label")

    def test_main_window_assemble_dialog_opens(
        self, qtbot, gui_project_dir_with_output
    ):
        """Assemble button should trigger assembly (no separate Preview button)."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir_with_output)

        # The old "Preview" action should not exist
        action_texts = [a.text() for a in window.toolbar.actions() if a.text()]
        assert "Preview" not in action_texts


# ---------------------------------------------------------------------------
# E2E tests: full workflow
# ---------------------------------------------------------------------------


class TestGuiEndToEnd:
    """End-to-end tests for the GUI workflow."""

    def test_open_project_and_select_scene_shows_preview(
        self, qtbot, gui_project_dir_with_output
    ):
        """Opening a project and selecting a generated scene shows its preview."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir_with_output)

        # Act — select scene 1 (generated)
        window.scene_list.list_widget.setCurrentRow(0)

        # Assert — preview should show an image
        assert not window.preview.image_label.pixmap().isNull()

    def test_scene_gen_finished_refreshes_preview(
        self, qtbot, gui_project_dir_with_output
    ):
        """After generation completes, the preview should update for the selected scene."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir_with_output)

        # Select scene 3 (pending still — no output yet)
        window.scene_list.list_widget.setCurrentRow(2)
        assert (
            window.preview._layout.currentWidget() is window.preview.placeholder_label
        )

        # Simulate generation completing: create the output file
        stills_dir = gui_project_dir_with_output / "output" / "stills"
        import struct
        import zlib

        def _make_png():
            signature = b"\x89PNG\r\n\x1a\n"

            def _chunk(chunk_type, data):
                c = chunk_type + data
                crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
                return struct.pack(">I", len(data)) + c + crc

            ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            raw = zlib.compress(b"\x00\xff\x00\x00")
            return (
                signature
                + _chunk(b"IHDR", ihdr)
                + _chunk(b"IDAT", raw)
                + _chunk(b"IEND", b"")
            )

        (stills_dir / "scene_03.png").write_bytes(_make_png())

        # Act — fire the scene_finished signal
        scene3 = window._project.scenes[2]
        window._on_scene_gen_finished(scene3)

        # Assert — preview should now show the image, not placeholder
        assert not window.preview.image_label.pixmap().isNull()

    def test_open_project_and_select_pending_scene_shows_placeholder(
        self, qtbot, gui_project_dir_with_output
    ):
        """Selecting a pending scene should show the placeholder."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir_with_output)

        # Act — select scene 3 (pending still)
        window.scene_list.list_widget.setCurrentRow(2)

        # Assert — placeholder should be the current stacked widget
        assert (
            window.preview._layout.currentWidget() is window.preview.placeholder_label
        )


# ---------------------------------------------------------------------------
# Unit tests: GenerateWorker stop flag
# ---------------------------------------------------------------------------


class TestGenerateWorkerStop:
    """Test the cooperative stop mechanism for GenerateWorker."""

    def test_worker_stop_flag_defaults_false(self, qtbot, gui_project_dir):
        """Worker should not be stopped by default."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        output_dir = gui_project_dir / "output"

        worker = GenerateWorker(
            scenes=project.scenes,
            project=project,
            output_dir=output_dir,
            project_dir=gui_project_dir,
        )

        assert not worker._stop_requested

    def test_worker_stops_after_current_scene(self, qtbot, gui_project_dir):
        """Worker should stop processing after current scene when stop is requested."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        output_dir = gui_project_dir / "output"

        finished_scenes = []

        def on_scene_finished(scene):
            finished_scenes.append(scene)
            # Request stop after first scene
            worker.request_stop()

        with (
            patch("storyboard_gen.gui.generate_worker.generate_still") as mock_still,
            patch("storyboard_gen.gui.generate_worker.generate_clip"),
        ):
            mock_still.return_value = output_dir / "stills" / "scene_01.png"

            worker = GenerateWorker(
                scenes=project.scenes,
                project=project,
                output_dir=output_dir,
                project_dir=gui_project_dir,
            )
            worker.scene_finished.connect(on_scene_finished)

            # Act
            worker.run()

            # Assert — only 1 scene should have been processed
            assert len(finished_scenes) == 1


# ---------------------------------------------------------------------------
# Unit tests: GenerateDialog
# ---------------------------------------------------------------------------


class TestGenerateDialog:
    """Test the generation options dialog."""

    def test_dialog_creates(self, qtbot, gui_project_dir_with_output):
        """GenerateDialog should instantiate with a project."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir_with_output)
        dialog = GenerateDialog(project)
        qtbot.addWidget(dialog)

        assert dialog is not None

    def test_dialog_all_stills_returns_still_scenes(
        self, qtbot, gui_project_dir_with_output
    ):
        """Selecting 'All stills' should return only still scenes."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir_with_output)
        dialog = GenerateDialog(project)
        qtbot.addWidget(dialog)

        # Act — select "All stills" radio
        dialog._radio_stills.setChecked(True)
        scenes = dialog.get_selected_scenes()

        # Assert
        assert all(s.scene_type == "still" for s in scenes)
        assert len(scenes) == 2  # scenes 1 and 3

    def test_dialog_all_clips_returns_clip_scenes(
        self, qtbot, gui_project_dir_with_output
    ):
        """Selecting 'All clips' should return only clip scenes."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir_with_output)
        dialog = GenerateDialog(project)
        qtbot.addWidget(dialog)

        # Act
        dialog._radio_clips.setChecked(True)
        scenes = dialog.get_selected_scenes()

        # Assert
        assert all(s.scene_type == "clip" for s in scenes)
        assert len(scenes) == 1  # scene 2

    def test_dialog_all_scenes_returns_all(self, qtbot, gui_project_dir_with_output):
        """Selecting 'All scenes' should return all scenes."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir_with_output)
        dialog = GenerateDialog(project)
        qtbot.addWidget(dialog)

        # Act
        dialog._radio_all.setChecked(True)
        scenes = dialog.get_selected_scenes()

        # Assert
        assert len(scenes) == 3


# ---------------------------------------------------------------------------
# Unit tests: YAML syntax highlighter
# ---------------------------------------------------------------------------


class TestYamlHighlighter:
    """Test the YAML syntax highlighting rules."""

    def test_highlighter_creates(self, qtbot):
        """YamlHighlighter should instantiate without error."""
        from PySide6.QtGui import QTextDocument

        from storyboard_gen.gui.yaml_viewer import YamlHighlighter

        doc = QTextDocument()
        highlighter = YamlHighlighter(doc)

        assert highlighter is not None

    def test_highlighter_has_rules(self, qtbot):
        """YamlHighlighter should have highlighting rules."""
        from PySide6.QtGui import QTextDocument

        from storyboard_gen.gui.yaml_viewer import YamlHighlighter

        doc = QTextDocument()
        highlighter = YamlHighlighter(doc)

        assert len(highlighter._rules) > 0


class TestYamlViewer:
    """Test the YAML viewer widget."""

    def test_viewer_creates(self, qtbot):
        """YamlViewer should instantiate without error."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)

        assert viewer is not None

    def test_viewer_loads_yaml_file(self, qtbot, gui_project_dir):
        """YamlViewer should display content from a YAML file."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)

        yaml_path = gui_project_dir / "project.yaml"

        # Act
        viewer.load_file(yaml_path)

        # Assert — should contain YAML content
        text = viewer.text_edit.toPlainText()
        assert "title" in text
        assert "scenes" in text

    def test_viewer_is_read_only(self, qtbot):
        """YamlViewer text area should be read-only."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)

        assert viewer.text_edit.isReadOnly()


# ---------------------------------------------------------------------------
# Integration tests: clip preview
# ---------------------------------------------------------------------------


class TestClipPreview:
    """Test clip preview in the preview panel."""

    def test_preview_shows_clip_info_for_existing_clip(
        self, qtbot, gui_project_dir_with_output
    ):
        """Preview panel should show clip info when a generated clip is selected."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        clip_path = gui_project_dir_with_output / "output" / "clips" / "scene_02.mp4"

        # Act
        panel.show_clip_info(clip_path)

        # Assert — should show clip info, not placeholder
        assert panel._layout.currentWidget() is not panel.placeholder_label

    def test_preview_clip_info_shows_filename(self, qtbot, gui_project_dir_with_output):
        """Clip info should include the filename."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        clip_path = gui_project_dir_with_output / "output" / "clips" / "scene_02.mp4"

        # Act
        panel.show_clip_info(clip_path)

        # Assert — clip info label should mention the filename
        assert "scene_02.mp4" in panel.clip_info_label.text()


# ---------------------------------------------------------------------------
# E2E: clip selection shows info
# ---------------------------------------------------------------------------


class TestClipSelectionEndToEnd:
    """E2E test for clip selection in the main window."""

    def test_selecting_generated_clip_shows_video_player(
        self, qtbot, gui_project_dir_with_output
    ):
        """Selecting a generated clip scene should show video player, not placeholder."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir_with_output)

        # Act — select scene 2 (clip, generated)
        window.scene_list.list_widget.setCurrentRow(1)

        # Assert — should show video player widget
        assert window.preview._layout.currentWidget() is window.preview._video_container


# ---------------------------------------------------------------------------
# Unit tests: video playback
# ---------------------------------------------------------------------------


class TestVideoPlayback:
    """Test inline video playback in the preview panel."""

    def test_preview_has_video_widget(self, qtbot):
        """PreviewPanel should have a _video_widget attribute for playback."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        # Assert
        assert hasattr(panel, "_video_widget")
        assert hasattr(panel, "_player")

    def test_play_clip_switches_to_video_view(self, qtbot, gui_project_dir_with_output):
        """Calling play_clip should switch stacked layout to video container."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        clip_path = gui_project_dir_with_output / "output" / "clips" / "scene_02.mp4"

        # Act
        panel.play_clip(clip_path)

        # Assert — video container should be current
        assert panel._layout.currentWidget() is panel._video_container

    def test_play_clip_sets_media_source(self, qtbot, gui_project_dir_with_output):
        """play_clip should set the media source on the player."""
        from PySide6.QtCore import QUrl

        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        clip_path = gui_project_dir_with_output / "output" / "clips" / "scene_02.mp4"

        # Act
        panel.play_clip(clip_path)

        # Assert — player source should match the clip path
        expected_url = QUrl.fromLocalFile(str(clip_path))
        assert panel._player.source() == expected_url

    def test_stop_playback_returns_to_placeholder(
        self, qtbot, gui_project_dir_with_output
    ):
        """stop_playback should stop the player and return to placeholder."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        clip_path = gui_project_dir_with_output / "output" / "clips" / "scene_02.mp4"
        panel.play_clip(clip_path)

        # Act
        panel.stop_playback()

        # Assert
        assert panel._layout.currentWidget() is panel.placeholder_label

    def test_clear_image_stops_playback(self, qtbot, gui_project_dir_with_output):
        """clear_image should also stop any active video playback."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        clip_path = gui_project_dir_with_output / "output" / "clips" / "scene_02.mp4"
        panel.play_clip(clip_path)

        # Act
        panel.clear_image()

        # Assert — should be back on placeholder
        assert panel._layout.currentWidget() is panel.placeholder_label

    def test_player_audio_is_muted(self, qtbot):
        """Video playback should be muted (no audio support yet)."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        # Assert
        assert panel._audio_output.isMuted()


# ---------------------------------------------------------------------------
# Unit tests: multi-select scenes
# ---------------------------------------------------------------------------


class TestMultiSelect:
    """Test multi-selection in SceneListWidget."""

    def test_scene_list_allows_multi_selection(
        self, qtbot, gui_project_dir_with_output
    ):
        """SceneListWidget should use ExtendedSelection mode."""
        from PySide6.QtWidgets import QAbstractItemView

        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Assert
        assert (
            widget.list_widget.selectionMode()
            == QAbstractItemView.SelectionMode.ExtendedSelection
        )

    def test_get_selected_scenes_returns_multiple(
        self, qtbot, gui_project_dir_with_output
    ):
        """Selecting multiple rows should return multiple scenes in order."""
        from PySide6.QtCore import QItemSelectionModel

        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Act — select rows 0 and 2 (skip row 1)
        model = widget.list_widget.model()
        sel_model = widget.list_widget.selectionModel()
        sel_model.select(model.index(0, 0), QItemSelectionModel.SelectionFlag.Select)
        sel_model.select(model.index(2, 0), QItemSelectionModel.SelectionFlag.Select)

        scenes = widget.get_selected_scenes()

        # Assert — should return scenes 1 and 3 in order
        assert len(scenes) == 2
        assert scenes[0].number == "1"
        assert scenes[1].number == "3"

    def test_get_selected_scenes_empty_when_none_selected(
        self, qtbot, gui_project_dir_with_output
    ):
        """No selection should return an empty list."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Act — clear any default selection
        widget.list_widget.clearSelection()

        scenes = widget.get_selected_scenes()

        # Assert
        assert scenes == []


# ---------------------------------------------------------------------------
# Unit tests: GenerateDialog with multi-select
# ---------------------------------------------------------------------------


class TestGenerateDialogMultiSelect:
    """Test GenerateDialog with multiple selected scenes."""

    def test_dialog_selected_scenes_returns_multiple(
        self, qtbot, gui_project_dir_with_output
    ):
        """Passing multiple scenes should enable radio and return them."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir_with_output)
        scenes = [project.scenes[0], project.scenes[2]]

        dialog = GenerateDialog(project, selected_scenes=scenes)
        qtbot.addWidget(dialog)

        # Act — select "Selected scenes" radio
        dialog._radio_selected.setChecked(True)
        result = dialog.get_selected_scenes()

        # Assert
        assert len(result) == 2
        assert result[0].number == "1"
        assert result[1].number == "3"
        assert dialog._radio_selected.isEnabled()
        assert "2 scenes" in dialog._radio_selected.text()

    def test_dialog_single_scene_shows_title(self, qtbot, gui_project_dir_with_output):
        """Passing a single scene should show its title."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir_with_output)
        scenes = [project.scenes[0]]

        dialog = GenerateDialog(project, selected_scenes=scenes)
        qtbot.addWidget(dialog)

        # Assert — should show scene title, not count
        assert "Opening shot" in dialog._radio_selected.text()


# ---------------------------------------------------------------------------
# Unit tests: OutputDialog
# ---------------------------------------------------------------------------


class TestOutputDialog:
    """Test the output options dialog."""

    def test_output_dialog_creates(self, qtbot):
        """OutputDialog should instantiate without error."""
        from storyboard_gen.gui.output_dialog import OutputDialog

        dialog = OutputDialog()
        qtbot.addWidget(dialog)

        assert dialog is not None

    def test_output_dialog_defaults_to_kdenlive(self, qtbot):
        """OutputDialog should default to kdenlive mode."""
        from storyboard_gen.gui.output_dialog import OutputDialog

        dialog = OutputDialog()
        qtbot.addWidget(dialog)

        # Assert
        options = dialog.get_options()
        assert options["mode"] == "kdenlive"

    def test_output_dialog_kdenlive_mode(self, qtbot):
        """Selecting kdenlive radio should return kdenlive mode."""
        from storyboard_gen.gui.output_dialog import OutputDialog

        dialog = OutputDialog()
        qtbot.addWidget(dialog)

        # Act
        dialog._radio_kdenlive.setChecked(True)
        options = dialog.get_options()

        # Assert
        assert options["mode"] == "kdenlive"

    def test_output_dialog_preview_mode(self, qtbot):
        """Checking preview checkbox should return preview=True."""
        from storyboard_gen.gui.output_dialog import OutputDialog

        dialog = OutputDialog()
        qtbot.addWidget(dialog)

        # Act
        dialog._preview_check.setChecked(True)
        options = dialog.get_options()

        # Assert
        assert options["preview"] is True


# ---------------------------------------------------------------------------
# Integration tests: MainWindow — Output and Refresh
# ---------------------------------------------------------------------------


class TestMainWindowOutputAndRefresh:
    """Test Output and Refresh toolbar actions in MainWindow."""

    def test_main_window_toolbar_has_output_and_refresh(self, qtbot):
        """MainWindow should have Output and Refresh actions instead of Assemble."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        action_texts = [a.text() for a in window.toolbar.actions() if a.text()]
        assert "Output" in action_texts
        assert "Refresh" in action_texts
        assert "Assemble" not in action_texts

    def test_main_window_refresh_reloads_project(
        self, qtbot, gui_project_dir_with_output
    ):
        """Refresh should reload the project from disk."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir_with_output)

        # Verify initial load
        assert window.scene_list.list_widget.count() == 3

        # Act — refresh
        window._on_refresh()

        # Assert — scene list should still be populated (reloaded)
        assert window.scene_list.list_widget.count() == 3
        assert "GUI Test Project" in window.windowTitle()


# ---------------------------------------------------------------------------
# Unit tests: error dialog surfacing
# ---------------------------------------------------------------------------


class TestErrorDialog:
    """Test that errors are surfaced via QMessageBox, not just the console."""

    def test_show_error_displays_message_box(self, qtbot):
        """_show_error should open a QMessageBox.critical dialog."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Patch QMessageBox.critical to capture the call
        with patch("storyboard_gen.gui.app.QMessageBox.critical") as mock_crit:
            window._show_error("Something broke")

            # Assert — message box was shown
            mock_crit.assert_called_once()
            args = mock_crit.call_args
            assert "Something broke" in args[0][2]  # message text

    def test_show_error_also_logs_to_console(self, qtbot):
        """_show_error should also append to the console panel."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        with patch("storyboard_gen.gui.app.QMessageBox.critical"):
            window._show_error("Something broke")

        # Assert — console should contain the error
        assert "Something broke" in window.console.text_edit.toPlainText()

    def test_generation_error_shows_message_box(self, qtbot, gui_project_dir):
        """Generation errors should pop a visible error dialog."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        with patch("storyboard_gen.gui.app.QMessageBox.critical") as mock_crit:
            window._on_gen_error("Scene 1: fal-client is not installed")

            mock_crit.assert_called_once()

    def test_config_error_shows_message_box(self, qtbot, tmp_path):
        """Config load errors should pop a visible error dialog."""
        from storyboard_gen.gui.app import MainWindow

        (tmp_path / "project.yaml").write_text("scenes: []")

        window = MainWindow()
        qtbot.addWidget(window)

        with patch("storyboard_gen.gui.app.QMessageBox.critical") as mock_crit:
            window.open_project(tmp_path)

            mock_crit.assert_called_once()
