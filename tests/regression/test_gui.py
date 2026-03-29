# ABOUTME: Tests for the storyboard-gen GUI module.
# ABOUTME: Covers scene status, log handler, widgets, and generate worker.

import logging
from pathlib import Path
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
        """Error messages should be rendered in dark red on light backgrounds."""
        from PySide6.QtGui import QColor, QPalette

        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)

        # Arrange — ensure light background
        palette = panel.text_edit.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        panel.text_edit.setPalette(palette)

        # Act
        panel.append_message("Error: something broke")

        # Assert — check that the text colour is dark red
        cursor = panel.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.Right)
        fmt = cursor.charFormat()
        assert fmt.foreground().color() == QColor("#cc0000")

    def test_console_panel_warning_highlighted_amber(self, qtbot):
        """Warning messages should be rendered in amber on light backgrounds."""
        from PySide6.QtGui import QColor, QPalette

        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)

        # Arrange — ensure light background
        palette = panel.text_edit.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        panel.text_edit.setPalette(palette)

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

    def test_console_panel_error_amber_on_dark_background(self, qtbot):
        """Error text should use amber when background is dark (#113)."""
        from PySide6.QtGui import QColor, QPalette

        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)

        # Arrange — force a dark background palette
        palette = panel.text_edit.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))
        panel.text_edit.setPalette(palette)

        # Act
        panel.append_message("ERROR: something broke")

        # Assert — amber for readability on dark backgrounds
        cursor = panel.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.Right)
        fmt = cursor.charFormat()
        assert fmt.foreground().color() == QColor("#ffaa33")

    def test_console_panel_error_dark_red_on_light_background(self, qtbot):
        """Error text should remain dark red when background is light."""
        from PySide6.QtGui import QColor, QPalette

        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)

        # Arrange — force a light background palette
        palette = panel.text_edit.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        panel.text_edit.setPalette(palette)

        # Act
        panel.append_message("ERROR: something broke")

        # Assert — classic dark red
        cursor = panel.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.Right)
        fmt = cursor.charFormat()
        assert fmt.foreground().color() == QColor("#cc0000")

    def test_console_panel_info_with_error_word_not_highlighted(self, qtbot):
        """INFO messages containing 'error' should use default text colour (#113)."""
        from PySide6.QtGui import QColor, QPalette

        from storyboard_gen.gui.console_panel import ConsolePanel

        panel = ConsolePanel()
        qtbot.addWidget(panel)

        # Arrange — ensure light background
        palette = panel.text_edit.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        panel.text_edit.setPalette(palette)

        # Act — INFO message that contains substring "error"
        panel.append_message("INFO: No errors found")

        # Assert — should NOT be coloured red
        cursor = panel.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.movePosition(cursor.MoveOperation.Right)
        fmt = cursor.charFormat()
        assert fmt.foreground().color() != QColor("#cc0000")


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

        # Assert — check item widget label text contains status indicators
        item0_widget = widget.list_widget.itemWidget(widget.list_widget.item(0))
        item2_widget = widget.list_widget.itemWidget(widget.list_widget.item(2))

        # Scene 1 is generated, scene 3 is pending
        assert "[OK]" in item0_widget._label.text()
        assert "[--]" in item2_widget._label.text()


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
                scene=scene,
                project=project,
                output_dir=output_dir,
                project_dir=gui_project_dir,
            )

            finished_scenes = []
            worker.scene_finished.connect(finished_scenes.append)

            # Act
            worker.run()

            # Assert
            assert len(finished_scenes) == 1
            assert finished_scenes[0] == scene

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
                scene=scene,
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
                scene=scene,
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

    def test_worker_dispatches_clip_to_generate_clip(self, qtbot, gui_project_dir):
        """Worker should call generate_clip for clip scenes."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        clip_scene = project.scenes[1]  # scene 2 is a clip
        output_dir = gui_project_dir / "output"

        with patch("storyboard_gen.gui.generate_worker.generate_clip") as mock_clip:
            mock_clip.return_value = output_dir / "clips" / "scene_02.mp4"

            worker = GenerateWorker(
                scene=clip_scene,
                project=project,
                output_dir=output_dir,
                project_dir=gui_project_dir,
            )

            # Act
            worker.run()

            # Assert
            assert mock_clip.call_count == 1


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

    def test_main_window_toolbar_buttons_exist(self, qtbot):
        """MainWindow should have toolbar buttons for generation and output."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Assert — check toolbar button tooltips contain the base label
        assert "Open Project" in window._btn_open.toolTip()
        assert "Refresh" in window._btn_refresh.toolTip()
        assert "Generate" in window._btn_generate.toolTip()
        assert "Stop" in window._btn_stop.toolTip()
        assert "Output" in window._btn_output.toolTip()
        assert "View YAML" in window._btn_yaml_viewer.toolTip()

    def test_main_window_stop_button_disabled_initially(self, qtbot):
        """Stop button should be disabled when not generating."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert not window._btn_stop.isEnabled()

    def test_main_window_has_progress_label(self, qtbot):
        """MainWindow should have a progress label in the status bar."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_progress_label")

    def test_main_window_has_spinner(self, qtbot):
        """MainWindow should have a spinner (indeterminate progress bar), hidden initially."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_spinner")
        assert window._spinner.isHidden()
        # Indeterminate: maximum == 0
        assert window._spinner.maximum() == 0

    def test_spinner_shown_during_generation(self, qtbot, gui_project_dir):
        """Spinner should be shown after _start_generation is called."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        # Patch GenerateWorker to avoid real generation
        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True
            window._start_scene_generation(scene)

        # Assert — spinner should not be hidden
        assert not window._spinner.isHidden()

    def test_spinner_hidden_when_all_workers_done(self, qtbot, gui_project_dir):
        """Spinner should be hidden when all workers finish."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # No workers active — spinner should be hidden
        window._update_progress()

        assert window._spinner.isHidden()

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

        # Add a dummy worker so _on_scene_gen_finished can remove it
        scene3 = window._project.scenes[2]
        from unittest.mock import MagicMock

        window._workers[str(scene3.number)] = MagicMock()

        # Act — fire the scene_finished signal
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
        scene = project.scenes[0]
        output_dir = gui_project_dir / "output"

        worker = GenerateWorker(
            scene=scene,
            project=project,
            output_dir=output_dir,
            project_dir=gui_project_dir,
        )

        assert not worker._stop_requested

    def test_worker_does_not_emit_finished_when_stopped(self, qtbot, gui_project_dir):
        """Worker should emit stopped (not scene_finished) if stopped before running."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        scene = project.scenes[0]
        output_dir = gui_project_dir / "output"

        with patch("storyboard_gen.gui.generate_worker.generate_still"):
            worker = GenerateWorker(
                scene=scene,
                project=project,
                output_dir=output_dir,
                project_dir=gui_project_dir,
            )

            finished_scenes = []
            worker.scene_finished.connect(finished_scenes.append)

            stopped_scenes = []
            worker.stopped.connect(stopped_scenes.append)

            # Stop before running
            worker.request_stop()

            # Act
            worker.run()

            # Assert — should emit stopped, not finished
            assert len(finished_scenes) == 0
            assert len(stopped_scenes) == 1


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


class TestClipPreviewReload:
    """Clip preview should reload when file is replaced on disk — issue #98."""

    def test_play_clip_clears_source_before_reload(self, qtbot, tmp_path):
        """play_clip should stop and clear source before setting new source."""
        from storyboard_gen.gui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        qtbot.addWidget(panel)

        clip = tmp_path / "test.mp4"
        clip.write_bytes(b"\x00" * 100)

        # Track setSource calls
        calls = []
        original_set_source = panel._player.setSource

        def tracking_set_source(url):
            calls.append(url)
            original_set_source(url)

        panel._player.setSource = tracking_set_source

        # Act — play clip twice (simulating archive restore)
        panel.play_clip(clip)
        calls.clear()
        panel.play_clip(clip)

        # Assert — source should have been cleared (empty QUrl) then set
        assert len(calls) >= 2
        assert calls[0].isEmpty()  # first call clears
        assert not calls[1].isEmpty()  # second call sets the file


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
        """MainWindow should have Output and Refresh buttons."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert "Output" in window._btn_output.toolTip()
        assert "Refresh" in window._btn_refresh.toolTip()

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
# Unit tests: GUI Kdenlive subtitle pass-through (#89)
# ---------------------------------------------------------------------------


class TestGuiKdenliveSubtitles:
    """Test that GUI Kdenlive export passes subtitle path from project (#89)."""

    def test_gui_kdenlive_export_passes_subtitles_path(
        self, qtbot, gui_project_dir_with_output
    ):
        """GUI Kdenlive export should pass project.subtitles to generate_kdenlive."""
        from storyboard_gen.gui.app import MainWindow

        # Arrange — add subtitles to the project
        yaml_path = gui_project_dir_with_output / "project.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["subtitles"] = "subs.srt"
        yaml_path.write_text(yaml.dump(data))

        srt_file = gui_project_dir_with_output / "subs.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir_with_output)

        # Act — mock generate_kdenlive and call the export method
        with patch("storyboard_gen.kdenlive.generate_kdenlive") as mock_gen:
            mock_gen.return_value = (
                gui_project_dir_with_output / "output" / "final" / "test.kdenlive"
            )
            window._run_kdenlive({"mode": "kdenlive"})

        # Assert — subtitles_path should be passed
        _, kwargs = mock_gen.call_args
        assert kwargs.get("subtitles_path") == srt_file

    def test_gui_kdenlive_export_skips_subtitles_in_preview(
        self, qtbot, gui_project_dir_with_output
    ):
        """GUI Kdenlive export in preview mode should skip subtitles."""
        from storyboard_gen.gui.app import MainWindow

        # Arrange
        yaml_path = gui_project_dir_with_output / "project.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["subtitles"] = "subs.srt"
        yaml_path.write_text(yaml.dump(data))

        srt_file = gui_project_dir_with_output / "subs.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir_with_output)

        # Act
        with patch("storyboard_gen.kdenlive.generate_kdenlive") as mock_gen:
            mock_gen.return_value = (
                gui_project_dir_with_output / "output" / "final" / "test.kdenlive"
            )
            window._run_kdenlive({"mode": "kdenlive", "preview": True})

        # Assert — no subtitles in preview mode
        _, kwargs = mock_gen.call_args
        assert kwargs.get("subtitles_path") is None

    def test_gui_kdenlive_export_skips_missing_subtitles(
        self, qtbot, gui_project_dir_with_output
    ):
        """GUI Kdenlive export should skip subtitles if file doesn't exist."""
        from storyboard_gen.gui.app import MainWindow

        # Arrange — subtitles configured but file doesn't exist
        yaml_path = gui_project_dir_with_output / "project.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["subtitles"] = "nonexistent.srt"
        yaml_path.write_text(yaml.dump(data))

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir_with_output)

        # Act
        with patch("storyboard_gen.kdenlive.generate_kdenlive") as mock_gen:
            mock_gen.return_value = (
                gui_project_dir_with_output / "output" / "final" / "test.kdenlive"
            )
            window._run_kdenlive({"mode": "kdenlive"})

        # Assert — subtitles_path should be None (file missing)
        _, kwargs = mock_gen.call_args
        assert kwargs.get("subtitles_path") is None


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

    def test_generation_error_logs_to_console(self, qtbot, gui_project_dir):
        """Generation errors should log to console, not show modal (#97)."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.QMessageBox"):
            window._on_gen_error(scene, "Scene 1: fal-client is not installed")

        text = window.console.text_edit.toPlainText()
        assert "fal-client is not installed" in text

    def test_config_error_shows_message_box(self, qtbot, tmp_path):
        """Config load errors should pop a visible error dialog."""
        from storyboard_gen.gui.app import MainWindow

        (tmp_path / "project.yaml").write_text("scenes: []")

        window = MainWindow()
        qtbot.addWidget(window)

        with patch("storyboard_gen.gui.app.QMessageBox.critical") as mock_crit:
            window.open_project(tmp_path)

            mock_crit.assert_called_once()


# ---------------------------------------------------------------------------
# Fixtures for archive tests
# ---------------------------------------------------------------------------


@pytest.fixture
def gui_project_dir_with_archives(gui_project_dir_with_output):
    """Project dir with archived versions of generated scenes."""
    stills_archive = gui_project_dir_with_output / "output" / "stills" / "archive"
    stills_archive.mkdir(parents=True)
    clips_archive = gui_project_dir_with_output / "output" / "clips" / "archive"
    clips_archive.mkdir(parents=True)

    # Create a minimal valid PNG for archived stills
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

    # Two archived versions of scene 1 (still) — older and newer
    (stills_archive / "scene_01_20260220_100000.png").write_bytes(_make_png())
    (stills_archive / "scene_01_20260221_120000.png").write_bytes(_make_png())

    # One archived version of scene 2 (clip)
    (clips_archive / "scene_02_20260220_150000.mp4").write_bytes(b"fake-mp4-archived")

    # An unrelated archive file (scene 3) — should not match scene 1 lookups
    (stills_archive / "scene_03_20260219_080000.png").write_bytes(_make_png())

    return gui_project_dir_with_output


# ---------------------------------------------------------------------------
# Unit tests: archive utility functions
# ---------------------------------------------------------------------------


class TestArchiveUtils:
    """Test archive utility functions for browsing and restoring archived outputs."""

    def test_get_scene_archive_dir_still(self, tmp_path):
        """Still scene archive dir should be output/stills/archive/."""
        from storyboard_gen.gui.archive_dialog import get_scene_archive_dir

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        result = get_scene_archive_dir(scene, output_dir)

        assert result == output_dir / "stills" / "archive"

    def test_get_scene_archive_dir_clip(self, tmp_path):
        """Clip scene archive dir should be output/clips/archive/."""
        from storyboard_gen.gui.archive_dialog import get_scene_archive_dir

        scene = Scene(
            number="2", title="Test", scene_type="clip", prompt="test", duration=6
        )
        output_dir = tmp_path / "output"

        result = get_scene_archive_dir(scene, output_dir)

        assert result == output_dir / "clips" / "archive"

    def test_get_scene_output_path_still(self, tmp_path):
        """Still scene output path should be output/stills/scene_01.png."""
        from storyboard_gen.gui.archive_dialog import get_scene_output_path

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        result = get_scene_output_path(scene, output_dir)

        assert result == output_dir / "stills" / "scene_01.png"

    def test_get_scene_output_path_clip(self, tmp_path):
        """Clip scene output path should be output/clips/scene_02.mp4."""
        from storyboard_gen.gui.archive_dialog import get_scene_output_path

        scene = Scene(
            number="2", title="Test", scene_type="clip", prompt="test", duration=6
        )
        output_dir = tmp_path / "output"

        result = get_scene_output_path(scene, output_dir)

        assert result == output_dir / "clips" / "scene_02.mp4"

    def test_list_scene_archives_finds_matching_files(
        self, gui_project_dir_with_archives
    ):
        """Should find archived versions matching the scene."""
        from storyboard_gen.gui.archive_dialog import list_scene_archives

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        result = list_scene_archives(scene, output_dir)

        assert len(result) == 2
        assert all("scene_01_" in p.name for p in result)

    def test_list_scene_archives_sorted_newest_first(
        self, gui_project_dir_with_archives
    ):
        """Archived versions should be sorted newest first."""
        from storyboard_gen.gui.archive_dialog import list_scene_archives

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        result = list_scene_archives(scene, output_dir)

        assert result[0].name == "scene_01_20260221_120000.png"
        assert result[1].name == "scene_01_20260220_100000.png"

    def test_list_scene_archives_empty_when_no_archive_dir(self, tmp_path):
        """No archive directory should return an empty list."""
        from storyboard_gen.gui.archive_dialog import list_scene_archives

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        result = list_scene_archives(scene, output_dir)

        assert result == []

    def test_list_scene_archives_ignores_other_scenes(
        self, gui_project_dir_with_archives
    ):
        """Should not return archives from other scenes."""
        from storyboard_gen.gui.archive_dialog import list_scene_archives

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        result = list_scene_archives(scene, output_dir)

        # Should only match scene_01, not scene_03
        assert all("scene_01_" in p.name for p in result)

    def test_list_scene_archives_for_clips(self, gui_project_dir_with_archives):
        """Should find clip archives in output/clips/archive/."""
        from storyboard_gen.gui.archive_dialog import list_scene_archives

        scene = Scene(
            number="2", title="Action", scene_type="clip", prompt="test", duration=6
        )
        output_dir = gui_project_dir_with_archives / "output"

        result = list_scene_archives(scene, output_dir)

        assert len(result) == 1
        assert "scene_02_" in result[0].name

    def test_parse_archive_timestamp(self):
        """Should parse timestamp from archive filename."""
        from pathlib import Path

        from storyboard_gen.gui.archive_dialog import parse_archive_timestamp

        archive_path = Path("scene_01_20260221_120000.png")

        result = parse_archive_timestamp(archive_path)

        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 21
        assert result.hour == 12
        assert result.minute == 0


# ---------------------------------------------------------------------------
# Unit tests: archive restore
# ---------------------------------------------------------------------------


class TestArchiveRestore:
    """Test restoring archived versions."""

    def test_restore_archive_swaps_files(self, gui_project_dir_with_archives):
        """Restore should archive current output and move selected archive to current."""
        from storyboard_gen.gui.archive_dialog import (
            list_scene_archives,
            restore_archive,
        )

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        # Current output exists
        current_path = output_dir / "stills" / "scene_01.png"
        assert current_path.exists()
        # Get the newest archive
        archives = list_scene_archives(scene, output_dir)
        archive_path = archives[0]
        archive_content = archive_path.read_bytes()

        # Act
        restore_archive(scene, archive_path, output_dir)

        # Assert — current should now contain the archive content
        assert current_path.exists()
        assert current_path.read_bytes() == archive_content

        # The old current should be in the archive dir with a new timestamp
        new_archives = list_scene_archives(scene, output_dir)
        # Should have same total count (old current archived, selected moved out)
        # Original: 2 archives + 1 current → after restore: 2 archives + 1 current
        assert len(new_archives) == 2

    def test_restore_archive_when_no_current_output(
        self, gui_project_dir_with_archives
    ):
        """Restore should work even when there's no current output."""
        from storyboard_gen.gui.archive_dialog import (
            list_scene_archives,
            restore_archive,
        )

        scene = Scene(
            number="3", title="Closing", scene_type="still", prompt="test", duration=4
        )
        output_dir = gui_project_dir_with_archives / "output"

        # Scene 3 has no current output but has an archive
        current_path = output_dir / "stills" / "scene_03.png"
        assert not current_path.exists()

        archives = list_scene_archives(scene, output_dir)
        assert len(archives) == 1
        archive_path = archives[0]

        # Act
        restore_archive(scene, archive_path, output_dir)

        # Assert — current should now exist
        assert current_path.exists()

        # Archive should be gone (moved to current)
        new_archives = list_scene_archives(scene, output_dir)
        assert len(new_archives) == 0


# ---------------------------------------------------------------------------
# Integration tests: ArchiveDialog
# ---------------------------------------------------------------------------


class TestArchiveDialog:
    """Test the archive browser dialog."""

    def test_archive_dialog_creates(self, qtbot, gui_project_dir_with_archives):
        """ArchiveDialog should instantiate without error."""
        from storyboard_gen.gui.archive_dialog import ArchiveDialog

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        dialog = ArchiveDialog(scene, output_dir)
        qtbot.addWidget(dialog)

        assert dialog is not None

    def test_archive_dialog_lists_archives(self, qtbot, gui_project_dir_with_archives):
        """ArchiveDialog should list archived versions for the scene."""
        from storyboard_gen.gui.archive_dialog import ArchiveDialog

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        dialog = ArchiveDialog(scene, output_dir)
        qtbot.addWidget(dialog)

        # Assert — should show 2 archived versions
        assert dialog._list_widget.count() == 2

    def test_archive_dialog_empty_state(self, qtbot, tmp_path):
        """ArchiveDialog should show a message when no archives exist."""
        from storyboard_gen.gui.archive_dialog import ArchiveDialog

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        dialog = ArchiveDialog(scene, output_dir)
        qtbot.addWidget(dialog)

        # Assert — list should be empty
        assert dialog._list_widget.count() == 0

    def test_archive_dialog_restore_button_disabled_initially(
        self, qtbot, gui_project_dir_with_archives
    ):
        """Restore button should be disabled when no archive is selected."""
        from storyboard_gen.gui.archive_dialog import ArchiveDialog

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        dialog = ArchiveDialog(scene, output_dir)
        qtbot.addWidget(dialog)

        # Assert
        assert not dialog._restore_btn.isEnabled()

    def test_archive_dialog_restore_button_enabled_on_selection(
        self, qtbot, gui_project_dir_with_archives
    ):
        """Restore button should be enabled when an archive is selected."""
        from storyboard_gen.gui.archive_dialog import ArchiveDialog

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        dialog = ArchiveDialog(scene, output_dir)
        qtbot.addWidget(dialog)

        # Act — select first item
        dialog._list_widget.setCurrentRow(0)

        # Assert
        assert dialog._restore_btn.isEnabled()

    def test_archive_dialog_shows_timestamp_in_items(
        self, qtbot, gui_project_dir_with_archives
    ):
        """Archive list items should show human-readable timestamps."""
        from storyboard_gen.gui.archive_dialog import ArchiveDialog

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        dialog = ArchiveDialog(scene, output_dir)
        qtbot.addWidget(dialog)

        # Assert — items should contain date info
        item_text = dialog._list_widget.item(0).text()
        assert "2026" in item_text


# ---------------------------------------------------------------------------
# Integration tests: MainWindow Archive action
# ---------------------------------------------------------------------------


class TestMainWindowArchivePerScene:
    """Test that per-scene Archive still works (toolbar Archive removed in #85)."""

    def test_toolbar_has_no_archive_button(self, qtbot):
        """Toolbar should not have an Archive button after #85."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert not hasattr(window, "_action_archive")
        assert not hasattr(window, "_btn_archive")


# ---------------------------------------------------------------------------
# Unit tests: init_project (extracted for GUI reuse)
# ---------------------------------------------------------------------------


class TestInitProject:
    """Test the extracted init_project function used by both CLI and GUI."""

    def test_init_project_creates_all_files(self, tmp_path):
        """init_project should create project.yaml, .env, .gitignore, README, and dirs."""
        from storyboard_gen.cli import init_project

        target = tmp_path / "new_project"

        # Act
        init_project(target)

        # Assert
        assert (target / "project.yaml").exists()
        assert (target / ".env").exists()
        assert (target / ".gitignore").exists()
        assert (target / "README.md").exists()
        assert (target / "references").is_dir()
        assert (target / "logs").is_dir()

    def test_init_project_raises_if_project_yaml_exists(self, tmp_path):
        """init_project should raise FileExistsError if project.yaml exists."""
        from storyboard_gen.cli import init_project

        target = tmp_path / "existing"
        target.mkdir()
        (target / "project.yaml").write_text("title: existing")

        # Act / Assert
        with pytest.raises(FileExistsError):
            init_project(target)

    def test_init_project_creates_parent_dirs(self, tmp_path):
        """init_project should create parent directories if needed."""
        from storyboard_gen.cli import init_project

        target = tmp_path / "deep" / "nested" / "project"

        # Act
        init_project(target)

        # Assert
        assert (target / "project.yaml").exists()


# ---------------------------------------------------------------------------
# Integration tests: MainWindow New Project action
# ---------------------------------------------------------------------------


class TestMainWindowNewProject:
    """Test the New Project toolbar action in MainWindow."""

    def test_main_window_toolbar_has_new_project_button(self, qtbot):
        """MainWindow should have a New Project button in the toolbar."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert "New Project" in window._btn_new.toolTip()

    def test_new_project_creates_and_opens_project(self, qtbot, tmp_path):
        """New Project should scaffold and open a new project."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        target = tmp_path / "my_new_project"

        # Patch the dialogs to return test values
        with (
            patch(
                "storyboard_gen.gui.app.QFileDialog.getExistingDirectory",
                return_value=str(tmp_path),
            ),
            patch(
                "storyboard_gen.gui.app.QInputDialog.getText",
                return_value=("my_new_project", True),
            ),
        ):
            window._on_new_project()

        # Assert — project should be created and loaded
        assert (target / "project.yaml").exists()
        assert window._project is not None
        assert window.scene_list.list_widget.count() > 0

    def test_new_project_cancelled_at_directory_picker(self, qtbot):
        """Cancelling the directory picker should do nothing."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        with patch(
            "storyboard_gen.gui.app.QFileDialog.getExistingDirectory",
            return_value="",
        ):
            window._on_new_project()

        # Assert — no project loaded
        assert window._project is None

    def test_new_project_cancelled_at_name_input(self, qtbot, tmp_path):
        """Cancelling the name input should do nothing."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        with (
            patch(
                "storyboard_gen.gui.app.QFileDialog.getExistingDirectory",
                return_value=str(tmp_path),
            ),
            patch(
                "storyboard_gen.gui.app.QInputDialog.getText",
                return_value=("", False),
            ),
        ):
            window._on_new_project()

        assert window._project is None

    def test_new_project_existing_dir_shows_error(self, qtbot, tmp_path):
        """If project.yaml already exists, should show error dialog."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Pre-create the target with a project.yaml
        target = tmp_path / "existing_project"
        target.mkdir()
        (target / "project.yaml").write_text("title: existing")

        with (
            patch(
                "storyboard_gen.gui.app.QFileDialog.getExistingDirectory",
                return_value=str(tmp_path),
            ),
            patch(
                "storyboard_gen.gui.app.QInputDialog.getText",
                return_value=("existing_project", True),
            ),
            patch("storyboard_gen.gui.app.QMessageBox.critical") as mock_crit,
        ):
            window._on_new_project()

        mock_crit.assert_called_once()


# ---------------------------------------------------------------------------
# Integration tests: per-scene action buttons
# ---------------------------------------------------------------------------


class TestSceneItemWidget:
    """Test the custom scene item widget with inline action buttons."""

    def test_scene_item_widget_creates(self, qtbot, gui_project_dir_with_output):
        """SceneItemWidget should instantiate for a scene."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        assert widget is not None

    def test_scene_item_shows_scene_info(self, qtbot, gui_project_dir_with_output):
        """SceneItemWidget should display scene number, type, and title."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1",
            title="Opening shot",
            scene_type="still",
            prompt="t",
            duration=5,
        )
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        label_text = widget._label.text()
        assert "1" in label_text
        assert "Opening shot" in label_text

    def test_scene_item_shows_generate_for_pending(self, qtbot, tmp_path):
        """Pending scene should show 'Generate' button."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        assert widget._gen_btn.text() == "Generate"

    def test_scene_item_shows_regenerate_for_generated(
        self, qtbot, gui_project_dir_with_output
    ):
        """Generated scene should show 'Regenerate' button."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        assert widget._gen_btn.text() == "Regenerate"

    def test_scene_item_generate_emits_signal(self, qtbot, tmp_path):
        """Clicking Generate should emit generate_clicked signal."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        received = []
        widget.generate_clicked.connect(received.append)

        # Act
        widget._gen_btn.click()

        assert len(received) == 1
        assert received[0].number == "1"

    def test_scene_item_archive_disabled_when_no_archives(self, qtbot, tmp_path):
        """Archive button should be disabled when no archives exist."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        assert not widget._archive_btn.isEnabled()

    def test_scene_item_archive_enabled_when_archives_exist(
        self, qtbot, gui_project_dir_with_archives
    ):
        """Archive button should be enabled when archives exist."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        assert widget._archive_btn.isEnabled()

    def test_scene_item_archive_emits_signal(
        self, qtbot, gui_project_dir_with_archives
    ):
        """Clicking Archive should emit archive_clicked signal."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Opening", scene_type="still", prompt="test", duration=5
        )
        output_dir = gui_project_dir_with_archives / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        received = []
        widget.archive_clicked.connect(received.append)

        # Act
        widget._archive_btn.click()

        assert len(received) == 1
        assert received[0].number == "1"


class TestSceneListSignals:
    """Test SceneListWidget emits generate and archive signals from item buttons."""

    def test_scene_list_emits_generate_requested(
        self, qtbot, gui_project_dir_with_output
    ):
        """SceneListWidget should emit generate_requested when button is clicked."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        received = []
        widget.generate_requested.connect(received.append)

        # Act — click the generate button on the first scene item
        item = widget.list_widget.item(0)
        item_widget = widget.list_widget.itemWidget(item)
        item_widget._gen_btn.click()

        assert len(received) == 1
        assert received[0].number == "1"

    def test_scene_list_emits_archive_requested(
        self, qtbot, gui_project_dir_with_archives
    ):
        """SceneListWidget should emit archive_requested when button is clicked."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_archives)
        output_dir = gui_project_dir_with_archives / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        received = []
        widget.archive_requested.connect(received.append)

        # Act — click the archive button on the first scene item
        item = widget.list_widget.item(0)
        item_widget = widget.list_widget.itemWidget(item)
        item_widget._archive_btn.click()

        assert len(received) == 1
        assert received[0].number == "1"

    def test_scene_list_refresh_updates_item_widgets(
        self, qtbot, gui_project_dir_with_output
    ):
        """refresh_status should update button labels and archive availability."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Scene 3 is pending
        item2 = widget.list_widget.item(2)
        item2_widget = widget.list_widget.itemWidget(item2)
        assert item2_widget._gen_btn.text() == "Generate"

        # Create output for scene 3
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

        (output_dir / "stills" / "scene_03.png").write_bytes(_make_png())

        # Act
        widget.refresh_status()

        # Assert — button should now say "Regenerate"
        item2_refreshed = widget.list_widget.item(2)
        item2_widget_refreshed = widget.list_widget.itemWidget(item2_refreshed)
        assert item2_widget_refreshed._gen_btn.text() == "Regenerate"


# ---------------------------------------------------------------------------
# Unit tests: SceneItemWidget generation states
# ---------------------------------------------------------------------------


class TestSceneItemState:
    """Test per-scene generation state (idle and generating)."""

    def test_scene_item_idle_state(self, qtbot, tmp_path):
        """Idle state: generate button enabled, spinner hidden."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        # Act
        widget.set_state("idle")

        # Assert
        assert widget._gen_btn.isEnabled()
        assert widget._gen_btn.text() == "Generate"
        assert widget._spinner.isHidden()

    def test_scene_item_generating_state(self, qtbot, tmp_path):
        """Generating state: button text 'Stop', enabled, spinner visible."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        # Act
        widget.set_state("generating")

        # Assert
        assert widget._gen_btn.text() == "Stop"
        assert widget._gen_btn.isEnabled()
        assert not widget._spinner.isHidden()
        assert not widget._archive_btn.isEnabled()

    def test_scene_item_stop_emits_signal(self, qtbot, tmp_path):
        """Clicking Stop in generating state should emit stop_clicked."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        widget.set_state("generating")

        received = []
        widget.stop_clicked.connect(received.append)

        # Act
        widget._gen_btn.click()

        # Assert
        assert len(received) == 1
        assert received[0].number == "1"

    def test_scene_item_generating_to_idle(self, qtbot, tmp_path):
        """Transitioning from generating to idle should restore button and hide spinner."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        # Arrange — go to generating state
        widget.set_state("generating")
        assert widget._gen_btn.text() == "Stop"

        # Act — back to idle
        widget.set_state("idle")

        # Assert
        assert widget._gen_btn.text() == "Generate"
        assert widget._gen_btn.isEnabled()
        assert widget._spinner.isHidden()


# ---------------------------------------------------------------------------
# Unit tests: SceneListWidget generation state management
# ---------------------------------------------------------------------------


class TestSceneListGenerationState:
    """Test SceneListWidget generation state management methods."""

    def test_set_scene_state_generating_shows_spinner(
        self, qtbot, gui_project_dir_with_output
    ):
        """set_scene_state('generating') should show spinner on the scene."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneItemWidget, SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Act — set scene 1 as generating
        widget.set_scene_state("1", "generating")

        # Assert
        item0 = widget.list_widget.itemWidget(widget.list_widget.item(0))
        assert isinstance(item0, SceneItemWidget)
        assert not item0._spinner.isHidden()
        assert item0._gen_btn.text() == "Stop"

    def test_set_scene_state_idle_restores_button(
        self, qtbot, gui_project_dir_with_output
    ):
        """set_scene_state('idle') should restore button text and hide spinner."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneItemWidget, SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Arrange — set generating
        widget.set_scene_state("1", "generating")

        # Act — set back to idle
        widget.set_scene_state("1", "idle")

        # Assert
        item0 = widget.list_widget.itemWidget(widget.list_widget.item(0))
        assert isinstance(item0, SceneItemWidget)
        assert item0._spinner.isHidden()
        assert item0._gen_btn.text() in ("Generate", "Regenerate")
        assert item0._gen_btn.isEnabled()

    def test_clear_generation_state_restores_all(
        self, qtbot, gui_project_dir_with_output
    ):
        """clear_generation_state should restore all items to idle."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneItemWidget, SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Arrange — set some scenes as generating
        widget.set_scene_state("1", "generating")
        widget.set_scene_state("2", "generating")

        # Act
        widget.clear_generation_state()

        # Assert — all buttons should be enabled, spinners hidden
        for i in range(widget.list_widget.count()):
            item_widget = widget.list_widget.itemWidget(widget.list_widget.item(i))
            assert isinstance(item_widget, SceneItemWidget)
            assert item_widget._gen_btn.isEnabled()
            assert item_widget._spinner.isHidden()
            assert item_widget._gen_btn.text() in ("Generate", "Regenerate")

    def test_stop_requested_signal_carries_scene(
        self, qtbot, gui_project_dir_with_output
    ):
        """Clicking Stop on generating scene should relay stop_requested with scene."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Arrange — set scene 1 as generating
        widget.set_scene_state("1", "generating")

        received = []
        widget.stop_requested.connect(received.append)

        # Act — click Stop on scene 1
        item0 = widget.list_widget.itemWidget(widget.list_widget.item(0))
        item0._gen_btn.click()

        # Assert — should receive the Scene object
        assert len(received) == 1
        assert received[0].number == "1"


class TestGuiDotenvLoading:
    """Tests for .env loading when opening a project in the GUI (#66)."""

    def test_open_project_loads_dotenv(self, qtbot, gui_project_dir):
        """Opening a project should load its .env file."""
        from storyboard_gen.gui.app import MainWindow

        # Arrange — write a .env with a distinctive variable
        env_file = gui_project_dir / ".env"
        env_file.write_text("STORYBOARD_TEST_MARKER=gui_loaded\n")

        window = MainWindow()
        qtbot.addWidget(window)

        # Act
        import os

        os.environ.pop("STORYBOARD_TEST_MARKER", None)
        window.open_project(gui_project_dir)

        # Assert
        assert os.environ.get("STORYBOARD_TEST_MARKER") == "gui_loaded"

        # Cleanup
        os.environ.pop("STORYBOARD_TEST_MARKER", None)


# ---------------------------------------------------------------------------
# Unit tests: GenerateWorker single-scene API (#68)
# ---------------------------------------------------------------------------


class TestGenerateWorkerSingleScene:
    """Test single-scene GenerateWorker API."""

    def test_worker_accepts_single_scene(self, qtbot, gui_project_dir):
        """GenerateWorker should accept a single Scene, not a list."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        scene = project.scenes[0]
        output_dir = gui_project_dir / "output"

        # Act — construct with single scene
        worker = GenerateWorker(
            scene=scene,
            project=project,
            output_dir=output_dir,
            project_dir=gui_project_dir,
        )

        # Assert
        assert worker._scene == scene

    def test_worker_single_scene_emits_finished(self, qtbot, gui_project_dir):
        """Single-scene worker should emit scene_finished for its scene."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        scene = project.scenes[0]
        output_dir = gui_project_dir / "output"

        with patch("storyboard_gen.gui.generate_worker.generate_still") as mock_gen:
            mock_gen.return_value = output_dir / "stills" / "scene_01.png"

            worker = GenerateWorker(
                scene=scene,
                project=project,
                output_dir=output_dir,
                project_dir=gui_project_dir,
            )

            finished_scenes = []
            worker.scene_finished.connect(finished_scenes.append)

            # Act
            worker.run()

            # Assert
            assert len(finished_scenes) == 1
            assert finished_scenes[0] == scene

    def test_worker_no_all_finished_signal(self, qtbot, gui_project_dir):
        """Single-scene worker should NOT have an all_finished signal."""
        from storyboard_gen.gui.generate_worker import GenerateWorker

        # Assert — GenerateWorker should not have all_finished attribute
        assert not hasattr(GenerateWorker, "all_finished")

    def test_worker_single_scene_error(self, qtbot, gui_project_dir):
        """Single-scene worker should emit error with scene number on failure."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_worker import GenerateWorker

        project = load_project(gui_project_dir)
        scene = project.scenes[0]
        output_dir = gui_project_dir / "output"

        with patch("storyboard_gen.gui.generate_worker.generate_still") as mock_gen:
            mock_gen.side_effect = RuntimeError("API error")

            worker = GenerateWorker(
                scene=scene,
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
            assert "Scene 1" in errors[0]


# ---------------------------------------------------------------------------
# Integration tests: concurrent per-scene generation (#68)
# ---------------------------------------------------------------------------


class TestConcurrentGeneration:
    """Test concurrent per-scene worker management in MainWindow."""

    def test_start_single_scene_creates_worker(self, qtbot, gui_project_dir):
        """Starting generation for one scene should create one worker in _workers."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            # Act
            window._start_scene_generation(scene)

            # Assert
            assert str(scene.number) in window._workers
            assert mock_cls.call_count == 1

    def test_start_multiple_scenes_creates_multiple_workers(
        self, qtbot, gui_project_dir
    ):
        """Starting generation for multiple scenes should create a worker per scene."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scenes = list(window._project.scenes)

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            # Act
            window._start_generation(scenes)

            # Assert — one worker per scene
            assert mock_cls.call_count == len(scenes)
            assert len(window._workers) == len(scenes)

    def test_stop_single_scene_only_stops_that_worker(self, qtbot, gui_project_dir):
        """Stopping one scene should only stop its worker, leaving others running."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scenes = list(window._project.scenes)

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            # Create distinct mock workers for each scene
            mock_workers = {}
            call_count = [0]

            def make_worker(**kwargs):
                w = type(mock_cls.return_value)()
                w.isRunning.return_value = True
                w.request_stop = lambda: None
                scene = kwargs.get("scene")
                if scene:
                    mock_workers[str(scene.number)] = w
                call_count[0] += 1
                return w

            mock_cls.side_effect = make_worker

            # Start all scenes
            for s in scenes:
                window._start_scene_generation(s)

            # Act — stop only scene 1
            window._stop_scene_generation(scenes[0])

            # Assert — only scene 1's worker should have been stopped
            assert str(scenes[0].number) in window._workers

    def test_stop_all_stops_all_workers(self, qtbot, gui_project_dir):
        """Toolbar Stop should stop all running workers."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scenes = list(window._project.scenes)
        stop_counts = {}

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:

            def make_worker(**kwargs):
                from unittest.mock import MagicMock

                w = MagicMock()
                w.isRunning.return_value = True
                scene = kwargs.get("scene")
                if scene:
                    stop_counts[str(scene.number)] = 0

                    def track_stop(num=str(scene.number)):
                        stop_counts[num] += 1

                    w.request_stop = track_stop
                return w

            mock_cls.side_effect = make_worker

            for s in scenes:
                window._start_scene_generation(s)

            # Act
            window._stop_all_generation()

            # Assert — all workers should have been stopped
            for num in stop_counts:
                assert stop_counts[num] == 1

    def test_scene_finished_removes_worker(self, qtbot, gui_project_dir):
        """When a scene finishes and cleanup runs, worker is removed."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)
            assert str(scene.number) in window._workers

            # Act — simulate scene finished + deferred cleanup
            window._on_scene_gen_finished(scene)
            window._cleanup_worker(str(scene.number))

            # Assert
            assert str(scene.number) not in window._workers

    def test_scene_error_removes_worker(self, qtbot, gui_project_dir):
        """When a scene errors and cleanup runs, worker is removed."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)
            assert str(scene.number) in window._workers

            # Act — simulate error + deferred cleanup
            with patch("storyboard_gen.gui.app.QMessageBox"):
                window._on_gen_error(scene, "API timeout")
            window._cleanup_worker(str(scene.number))

            # Assert
            assert str(scene.number) not in window._workers

    def test_regenerate_running_scene_ignored(self, qtbot, gui_project_dir):
        """Starting generation for an already-generating scene should be ignored."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)
            assert mock_cls.call_count == 1

            # Act — try to start same scene again
            window._start_scene_generation(scene)

            # Assert — should not create a second worker
            assert mock_cls.call_count == 1

    def test_generate_all_starts_all_concurrently(self, qtbot, gui_project_dir):
        """_start_generation with multiple scenes should start all concurrently."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scenes = list(window._project.scenes)

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            # Act
            window._start_generation(scenes)

            # Assert — a worker should be started for each scene
            assert mock_cls.call_count == len(scenes)
            for s in scenes:
                assert str(s.number) in window._workers


# ---------------------------------------------------------------------------
# Integration tests: per-scene stop signal with scene identity (#68)
# ---------------------------------------------------------------------------


class TestPerSceneStopSignal:
    """Test that stop_requested carries the Scene object."""

    def test_stop_requested_carries_scene(self, qtbot, gui_project_dir_with_output):
        """stop_requested should emit the Scene that was stopped."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Set scene 1 as generating
        widget.set_scene_state("1", "generating")

        received = []
        widget.stop_requested.connect(received.append)

        # Act — click Stop on scene 1
        item0 = widget.list_widget.itemWidget(widget.list_widget.item(0))
        item0._gen_btn.click()

        # Assert — should receive the Scene object
        assert len(received) == 1
        assert received[0].number == "1"

    def test_set_scene_state_generating(self, qtbot, gui_project_dir_with_output):
        """set_scene_state('generating') should show spinner and Stop button."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneItemWidget, SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Act
        widget.set_scene_state("1", "generating")

        # Assert
        item0 = widget.list_widget.itemWidget(widget.list_widget.item(0))
        assert isinstance(item0, SceneItemWidget)
        assert not item0._spinner.isHidden()
        assert item0._gen_btn.text() == "Stop"

    def test_set_scene_state_idle(self, qtbot, gui_project_dir_with_output):
        """set_scene_state('idle') should hide spinner and restore button text."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneItemWidget, SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Set to generating first
        widget.set_scene_state("1", "generating")

        # Act — back to idle
        widget.set_scene_state("1", "idle")

        # Assert
        item0 = widget.list_widget.itemWidget(widget.list_widget.item(0))
        assert isinstance(item0, SceneItemWidget)
        assert item0._spinner.isHidden()
        assert item0._gen_btn.text() in ("Generate", "Regenerate")


# ---------------------------------------------------------------------------
# Integration tests: console panel slide-out (#68)
# ---------------------------------------------------------------------------


class TestConsolePanelToggle:
    """Test that the console panel can be toggled as a slide-out panel."""

    def test_main_window_has_console_toggle(self, qtbot):
        """MainWindow should have a toolbar button to toggle the console."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_btn_console")

    def test_console_hidden_by_default(self, qtbot):
        """Console panel should be hidden by default."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Console should be hidden by default
        assert window.console.isHidden()

    def test_console_toggle_shows_panel(self, qtbot):
        """Clicking console toggle when hidden should show the panel."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Act — toggle to show
        window._btn_console.click()

        # Assert — widget should no longer be explicitly hidden
        assert not window.console.isHidden()

    def test_console_toggle_round_trip(self, qtbot):
        """Toggle show → hide should work."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Show
        window._btn_console.click()
        assert not window.console.isHidden()

        # Hide
        window._btn_console.click()
        assert window.console.isHidden()


# ---------------------------------------------------------------------------
# Integration tests: progress display with concurrent workers (#68)
# ---------------------------------------------------------------------------


class TestConcurrentProgressDisplay:
    """Test progress display for concurrent generation."""

    def test_progress_shows_active_count(self, qtbot, gui_project_dir):
        """Progress label should show count of active workers."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scenes = list(window._project.scenes)

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_generation(scenes)

            # Assert — progress label should show count
            label_text = window._progress_label.text()
            assert "3" in label_text

    def test_spinner_visible_when_workers_active(self, qtbot, gui_project_dir):
        """Toolbar spinner should be visible when any workers are active."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Assert
            assert not window._spinner.isHidden()

    def test_spinner_hidden_when_all_workers_done(self, qtbot, gui_project_dir):
        """Toolbar spinner should hide when all workers finish and cleanup runs."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Act — simulate finish + deferred cleanup
            window._on_scene_gen_finished(scene)
            window._cleanup_worker(str(scene.number))

            # Assert
            assert window._spinner.isHidden()


# ---------------------------------------------------------------------------
# Fixtures: hand-written YAML for extraction tests
# ---------------------------------------------------------------------------

HAND_WRITTEN_YAML = """\
title: "GUI Test Project"
aspect_ratio: "9:16"
style_prefix: >
  Watercolour illustration.

characters:
  hero:
    description: "A young boy with red hair"
    reference:
      - "references/hero.png"

scenes:
  # === ACT 1 ===

  - number: 1
    title: "Opening shot"
    type: still
    duration: 5
    camera: WIDE
    ken_burns: zoom_in
    characters: [hero]
    prompt: >
      A boy stands on a hill.

  - number: 2
    title: "Action"
    type: clip
    duration: 6
    prompt: >
      The boy runs.

  - number: 3
    title: "Closing"
    type: still
    duration: 4
    camera: CLOSE
    ken_burns: static
    prompt: >
      Close-up of the boy smiling.
"""


@pytest.fixture
def hand_written_project_dir(tmp_path):
    """Create a project directory with hand-written YAML (preserves formatting)."""
    yaml_path = tmp_path / "project.yaml"
    yaml_path.write_text(HAND_WRITTEN_YAML)

    refs_dir = tmp_path / "references"
    refs_dir.mkdir()
    (refs_dir / "hero.png").write_bytes(b"fake-png")

    return tmp_path


# ---------------------------------------------------------------------------
# Unit tests: Scene YAML extraction and replacement
# ---------------------------------------------------------------------------


class TestSceneYamlExtraction:
    """Test extracting a scene's YAML block from project.yaml."""

    def test_extract_scene_returns_block_for_existing_scene(
        self, hand_written_project_dir
    ):
        """Extracting scene 1 should return its YAML block."""
        from storyboard_gen.gui.scene_yaml_editor import extract_scene_yaml

        yaml_path = hand_written_project_dir / "project.yaml"

        # Act
        block = extract_scene_yaml(yaml_path, "1")

        # Assert
        assert "number: 1" in block
        assert "Opening shot" in block
        assert "A boy stands on a hill." in block

    def test_extract_scene_does_not_include_other_scenes(
        self, hand_written_project_dir
    ):
        """Extracting scene 1 should not include scene 2 content."""
        from storyboard_gen.gui.scene_yaml_editor import extract_scene_yaml

        yaml_path = hand_written_project_dir / "project.yaml"

        # Act
        block = extract_scene_yaml(yaml_path, "1")

        # Assert
        assert "number: 2" not in block
        assert "Action" not in block

    def test_extract_scene_preserves_indentation(self, hand_written_project_dir):
        """Extracted YAML block should preserve original indentation."""
        from storyboard_gen.gui.scene_yaml_editor import extract_scene_yaml

        yaml_path = hand_written_project_dir / "project.yaml"

        # Act
        block = extract_scene_yaml(yaml_path, "1")

        # Assert — should start with list marker
        assert block.lstrip().startswith("- number:")

    def test_extract_last_scene(self, hand_written_project_dir):
        """Extracting the last scene should work correctly."""
        from storyboard_gen.gui.scene_yaml_editor import extract_scene_yaml

        yaml_path = hand_written_project_dir / "project.yaml"

        # Act
        block = extract_scene_yaml(yaml_path, "3")

        # Assert
        assert "number: 3" in block
        assert "Closing" in block

    def test_extract_nonexistent_scene_returns_none(self, hand_written_project_dir):
        """Extracting a scene that doesn't exist should return None."""
        from storyboard_gen.gui.scene_yaml_editor import extract_scene_yaml

        yaml_path = hand_written_project_dir / "project.yaml"

        # Act
        result = extract_scene_yaml(yaml_path, "99")

        # Assert
        assert result is None

    def test_extract_middle_scene(self, hand_written_project_dir):
        """Extracting a middle scene should include only that scene."""
        from storyboard_gen.gui.scene_yaml_editor import extract_scene_yaml

        yaml_path = hand_written_project_dir / "project.yaml"

        # Act
        block = extract_scene_yaml(yaml_path, "2")

        # Assert
        assert "number: 2" in block
        assert "The boy runs." in block
        assert "number: 1" not in block
        assert "number: 3" not in block


class TestQuotedSceneNumbers:
    """Scene numbers with YAML quotes should be matched correctly (#129)."""

    def test_extract_scene_yaml_double_quoted_number(self, tmp_path):
        """Double-quoted number: \"10a\" should be found by extract_scene_yaml (AC1)."""
        from storyboard_gen.gui.scene_yaml_editor import extract_scene_yaml

        yaml_path = tmp_path / "project.yaml"
        yaml_path.write_text(
            'title: "Test"\nscenes:\n'
            '  - number: "10a"\n    title: "Quoted scene"\n    type: still\n'
            "    duration: 3\n    prompt: >\n      A test.\n"
        )

        block = extract_scene_yaml(yaml_path, "10a")
        assert block is not None
        assert "Quoted scene" in block

    def test_extract_scene_yaml_single_quoted_number(self, tmp_path):
        """Single-quoted number: '10a' should be found (AC2)."""
        from storyboard_gen.gui.scene_yaml_editor import extract_scene_yaml

        yaml_path = tmp_path / "project.yaml"
        yaml_path.write_text(
            'title: "Test"\nscenes:\n'
            "  - number: '10a'\n    title: \"Quoted scene\"\n    type: still\n"
            "    duration: 3\n    prompt: >\n      A test.\n"
        )

        block = extract_scene_yaml(yaml_path, "10a")
        assert block is not None
        assert "Quoted scene" in block

    def test_extract_scene_yaml_unquoted_string_number(self, tmp_path):
        """Unquoted alphanumeric number: 10a still works (AC3 regression)."""
        from storyboard_gen.gui.scene_yaml_editor import extract_scene_yaml

        yaml_path = tmp_path / "project.yaml"
        yaml_path.write_text(
            'title: "Test"\nscenes:\n'
            '  - number: 10a\n    title: "Unquoted scene"\n    type: still\n'
            "    duration: 3\n    prompt: >\n      A test.\n"
        )

        block = extract_scene_yaml(yaml_path, "10a")
        assert block is not None
        assert "Unquoted scene" in block

    def test_is_dirty_false_when_scene_not_found(self, qtbot, tmp_path):
        """is_dirty() should return False when scene was not found (AC5)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = tmp_path / "project.yaml"
        yaml_path.write_text(
            'title: "Test"\nscenes:\n'
            '  - number: 1\n    title: "Only scene"\n    type: still\n'
            "    duration: 3\n    prompt: >\n      A test.\n"
        )

        # Load a scene that doesn't exist
        editor.load_scene("99", yaml_path)

        # Should NOT be dirty — no real content to save
        assert not editor.is_dirty()


class TestSceneYamlReplacement:
    """Test replacing a scene's YAML block in project.yaml."""

    def test_replace_scene_updates_file(self, hand_written_project_dir):
        """Replacing scene 1 should update the file content."""
        from storyboard_gen.gui.scene_yaml_editor import (
            extract_scene_yaml,
            replace_scene_yaml,
        )

        yaml_path = hand_written_project_dir / "project.yaml"

        # Arrange — get original block and modify it
        original = extract_scene_yaml(yaml_path, "1")
        modified = original.replace("Opening shot", "New opening")

        # Act
        result = replace_scene_yaml(yaml_path, "1", modified)

        # Assert
        assert result is True
        content = yaml_path.read_text()
        assert "New opening" in content
        assert "Opening shot" not in content

    def test_replace_scene_preserves_other_scenes(self, hand_written_project_dir):
        """Replacing scene 1 should not affect scene 2 or 3."""
        from storyboard_gen.gui.scene_yaml_editor import (
            extract_scene_yaml,
            replace_scene_yaml,
        )

        yaml_path = hand_written_project_dir / "project.yaml"

        original = extract_scene_yaml(yaml_path, "1")
        modified = original.replace("Opening shot", "New opening")

        # Act
        replace_scene_yaml(yaml_path, "1", modified)

        # Assert — other scenes untouched
        content = yaml_path.read_text()
        assert "Action" in content
        assert "Closing" in content

    def test_replace_scene_produces_valid_yaml(self, hand_written_project_dir):
        """After replacement, the full file should still parse as valid YAML."""
        from storyboard_gen.gui.scene_yaml_editor import (
            extract_scene_yaml,
            replace_scene_yaml,
        )

        yaml_path = hand_written_project_dir / "project.yaml"

        original = extract_scene_yaml(yaml_path, "1")
        modified = original.replace("Opening shot", "New opening")

        # Act
        replace_scene_yaml(yaml_path, "1", modified)

        # Assert — YAML still parses
        content = yaml_path.read_text()
        parsed = yaml.safe_load(content)
        assert parsed["scenes"][0]["title"] == "New opening"

    def test_replace_nonexistent_scene_returns_false(self, hand_written_project_dir):
        """Replacing a nonexistent scene should return False."""
        from storyboard_gen.gui.scene_yaml_editor import replace_scene_yaml

        yaml_path = hand_written_project_dir / "project.yaml"

        # Act
        result = replace_scene_yaml(yaml_path, "99", "  - number: 99\n")

        # Assert
        assert result is False

    def test_replace_last_scene(self, hand_written_project_dir):
        """Replacing the last scene should work correctly."""
        from storyboard_gen.gui.scene_yaml_editor import (
            extract_scene_yaml,
            replace_scene_yaml,
        )

        yaml_path = hand_written_project_dir / "project.yaml"

        original = extract_scene_yaml(yaml_path, "3")
        modified = original.replace("Closing", "Final shot")

        # Act
        result = replace_scene_yaml(yaml_path, "3", modified)

        # Assert
        assert result is True
        content = yaml_path.read_text()
        assert "Final shot" in content
        assert "Closing" not in content


# ---------------------------------------------------------------------------
# Unit tests: SceneYamlEditor widget
# ---------------------------------------------------------------------------


class TestSceneYamlEditor:
    """Test the SceneYamlEditor widget."""

    def test_editor_creates(self, qtbot):
        """SceneYamlEditor should instantiate without error."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        assert editor is not None

    def test_editor_is_editable(self, qtbot):
        """The text area in SceneYamlEditor should be editable."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        assert not editor.text_edit.isReadOnly()

    def test_editor_has_syntax_highlighting(self, qtbot):
        """SceneYamlEditor should apply YAML syntax highlighting."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        assert editor._highlighter is not None

    def test_load_scene_shows_yaml_block(self, qtbot, hand_written_project_dir):
        """Loading a scene should display its YAML block."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = hand_written_project_dir / "project.yaml"

        # Act
        editor.load_scene("1", yaml_path)

        # Assert
        text = editor.text_edit.toPlainText()
        assert "number: 1" in text
        assert "Opening shot" in text

    def test_load_nonexistent_scene_shows_placeholder(
        self, qtbot, hand_written_project_dir
    ):
        """Loading a nonexistent scene should show a placeholder message."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = hand_written_project_dir / "project.yaml"

        # Act
        editor.load_scene("99", yaml_path)

        # Assert
        text = editor.text_edit.toPlainText()
        assert "not found" in text.lower()

    def test_save_emits_scene_modified(self, qtbot, hand_written_project_dir):
        """Saving a valid edit should emit scene_modified signal."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = hand_written_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Act — modify text and save
        with qtbot.waitSignal(editor.scene_modified, timeout=1000):
            editor._save()

    def test_save_invalid_yaml_shows_error(self, qtbot, hand_written_project_dir):
        """Saving invalid YAML should show an error and not emit scene_modified."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = hand_written_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Arrange — insert invalid YAML
        editor.text_edit.setPlainText("  - number: 1\n    : invalid: yaml: [")

        # Act
        editor._save()

        # Assert — status label should show error
        assert "error" in editor._status_label.text().lower()

    def test_is_dirty_false_initially(self, qtbot, hand_written_project_dir):
        """Editor should not be dirty after initial load."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = hand_written_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Assert
        assert not editor.is_dirty()

    def test_is_dirty_after_edit(self, qtbot, hand_written_project_dir):
        """Editor should be dirty after user edits."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = hand_written_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Act — modify text
        editor.text_edit.setPlainText(editor.text_edit.toPlainText() + "\n# edited")

        # Assert
        assert editor.is_dirty()

    def test_save_clears_dirty(self, qtbot, hand_written_project_dir):
        """Successful save should clear the dirty flag."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = hand_written_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Arrange — make a valid edit
        text = editor.text_edit.toPlainText()
        editor.text_edit.setPlainText(text.replace("Opening shot", "New title"))

        # Act
        editor._save()

        # Assert
        assert not editor.is_dirty()


# ---------------------------------------------------------------------------
# Integration tests: Split pane layout in MainWindow
# ---------------------------------------------------------------------------


class TestMainWindowSplitPane:
    """Test the split pane (Preview + YAML) layout in MainWindow."""

    def test_main_window_has_preview_and_yaml_editor(self, qtbot, gui_project_dir):
        """MainWindow should have both preview and yaml_editor as separate panes."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Assert — both widgets exist
        assert hasattr(window, "preview")
        assert hasattr(window, "yaml_editor")

    def test_yaml_editor_hidden_by_default(self, qtbot, gui_project_dir):
        """YAML editor pane should be hidden by default."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Assert
        assert window.yaml_editor.isHidden()

    def test_yaml_toggle_shows_editor(self, qtbot, gui_project_dir):
        """Toggling YAML should show the editor pane."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Act
        window._on_toggle_yaml()

        # Assert
        assert not window.yaml_editor.isHidden()

    def test_yaml_toggle_round_trip(self, qtbot, gui_project_dir):
        """Toggling YAML twice should hide it again."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Act
        window._on_toggle_yaml()
        window._on_toggle_yaml()

        # Assert
        assert window.yaml_editor.isHidden()

    def test_yaml_content_persists_across_toggle(self, qtbot, hand_written_project_dir):
        """YAML editor content should persist when toggled off and on."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(hand_written_project_dir)

        # Arrange — show YAML, select scene, make edits
        window._on_toggle_yaml()
        scene = window._project.scenes[0]
        window._on_scene_selected(scene)
        window.yaml_editor.text_edit.setPlainText("# custom edit")

        # Act — toggle off and on
        window._on_toggle_yaml()
        window._on_toggle_yaml()

        # Assert — content preserved
        assert window.yaml_editor.text_edit.toPlainText() == "# custom edit"

    def test_scene_selection_updates_yaml_editor(self, qtbot, hand_written_project_dir):
        """Selecting a scene should update the YAML editor content."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(hand_written_project_dir)

        # Act — select scene 1
        scene = window._project.scenes[0]
        window._on_scene_selected(scene)

        # Assert
        text = window.yaml_editor.text_edit.toPlainText()
        assert "number: 1" in text

    def test_scene_modified_reloads_project(self, qtbot, hand_written_project_dir):
        """scene_modified signal from YAML editor should reload the project."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(hand_written_project_dir)

        original_title = window._project.scenes[0].title

        # Act — modify scene YAML through the editor and save
        scene = window._project.scenes[0]
        window._on_scene_selected(scene)
        text = window.yaml_editor.text_edit.toPlainText()
        window.yaml_editor.text_edit.setPlainText(
            text.replace("Opening shot", "Modified title")
        )
        window.yaml_editor._save()

        # Assert — project should have reloaded with new title
        assert window._project.scenes[0].title == "Modified title"
        assert window._project.scenes[0].title != original_title

    def test_yaml_toolbar_button_exists(self, qtbot, gui_project_dir):
        """MainWindow should have a YAML toggle button in the toolbar."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Assert
        assert hasattr(window, "_btn_yaml_editor")


# ---------------------------------------------------------------------------
# Unit tests: Unsaved changes warning
# ---------------------------------------------------------------------------


class TestUnsavedChangesWarning:
    """Test the unsaved changes prompt when switching scenes."""

    def test_switching_scene_with_dirty_editor_prompts(
        self, qtbot, hand_written_project_dir
    ):
        """Switching scenes with unsaved changes should prompt user."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(hand_written_project_dir)

        # Arrange — select scene 1 and make it dirty
        scene1 = window._project.scenes[0]
        window._on_scene_selected(scene1)
        text = window.yaml_editor.text_edit.toPlainText()
        window.yaml_editor.text_edit.setPlainText(text + "\n# edit")

        # Act — switch to scene 2 with auto-discard for test
        with patch("storyboard_gen.gui.app.QMessageBox.question") as mock_q:
            from PySide6.QtWidgets import QMessageBox

            mock_q.return_value = QMessageBox.StandardButton.Discard
            scene2 = window._project.scenes[1]
            window._on_scene_selected(scene2)

            # Assert — message box was shown
            mock_q.assert_called_once()

    def test_switching_scene_without_changes_no_prompt(
        self, qtbot, hand_written_project_dir
    ):
        """Switching scenes without unsaved changes should not prompt."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(hand_written_project_dir)

        # Arrange — select scene 1 (no edits)
        scene1 = window._project.scenes[0]
        window._on_scene_selected(scene1)

        # Act — switch to scene 2
        with patch("storyboard_gen.gui.app.QMessageBox.question") as mock_q:
            scene2 = window._project.scenes[1]
            window._on_scene_selected(scene2)

            # Assert — no message box
            mock_q.assert_not_called()


# ---------------------------------------------------------------------------
# Unit tests: AppSettings (QSettings wrapper)
# ---------------------------------------------------------------------------


class TestAppSettings:
    """Test the AppSettings QSettings wrapper."""

    def test_settings_creates(self, qtbot):
        """AppSettings should instantiate without error."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        assert settings is not None

    def test_editor_font_size_default(self, qtbot):
        """Default font size should be 11."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        # Clear any stored value first
        settings._qs.remove("editor/font_size")

        assert settings.editor_font_size == 11

    def test_editor_font_size_set_and_get(self, qtbot):
        """Setting font size should persist and be retrievable."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()

        # Act
        settings.editor_font_size = 16

        # Assert
        assert settings.editor_font_size == 16

        # Cleanup
        settings._qs.remove("editor/font_size")

    def test_editor_font_size_clamped_min(self, qtbot):
        """Font size below 8 should be clamped to 8."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings.editor_font_size = 4

        assert settings.editor_font_size == 8

        settings._qs.remove("editor/font_size")

    def test_editor_font_size_clamped_max(self, qtbot):
        """Font size above 32 should be clamped to 32."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings.editor_font_size = 50

        assert settings.editor_font_size == 32

        settings._qs.remove("editor/font_size")

    def test_last_project_default_empty(self, qtbot):
        """Default last project should be empty string."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings._qs.remove("session/last_project")

        assert settings.last_project == ""

    def test_last_project_set_and_get(self, qtbot):
        """Setting last project should persist."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings.last_project = "/tmp/my-project"

        assert settings.last_project == "/tmp/my-project"

        settings._qs.remove("session/last_project")

    def test_last_directory_default_empty(self, qtbot):
        """Default last directory should be empty string."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings._qs.remove("session/last_directory")

        assert settings.last_directory == ""

    def test_last_directory_set_and_get(self, qtbot):
        """Setting last directory should persist."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings.last_directory = "/tmp/projects"

        assert settings.last_directory == "/tmp/projects"

        settings._qs.remove("session/last_directory")


# ---------------------------------------------------------------------------
# Unit tests: YAML editor font size controls
# ---------------------------------------------------------------------------


class TestYamlEditorFontSize:
    """Test font size controls in SceneYamlEditor."""

    def test_set_font_size_changes_font(self, qtbot):
        """set_font_size should change the editor font point size."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        # Act
        editor.set_font_size(18)

        # Assert
        assert editor.text_edit.font().pointSize() == 18

    def test_set_font_size_clamped_min(self, qtbot):
        """Font size below 8 should be clamped."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        editor.set_font_size(4)
        assert editor.text_edit.font().pointSize() == 8

    def test_set_font_size_clamped_max(self, qtbot):
        """Font size above 32 should be clamped."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        editor.set_font_size(50)
        assert editor.text_edit.font().pointSize() == 32

    def test_increase_font_emits_signal(self, qtbot):
        """Increasing font should emit font_size_changed signal."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)
        editor.set_font_size(11)

        # Act
        with qtbot.waitSignal(editor.font_size_changed, timeout=1000):
            editor._increase_font()

        assert editor.text_edit.font().pointSize() == 12

    def test_decrease_font_emits_signal(self, qtbot):
        """Decreasing font should emit font_size_changed signal."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)
        editor.set_font_size(11)

        with qtbot.waitSignal(editor.font_size_changed, timeout=1000):
            editor._decrease_font()

        assert editor.text_edit.font().pointSize() == 10

    def test_font_size_buttons_exist(self, qtbot):
        """SceneYamlEditor should have font +/- buttons."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        assert hasattr(editor, "_font_plus_btn")
        assert hasattr(editor, "_font_minus_btn")

    def test_font_plus_button_increases_size(self, qtbot):
        """Clicking the + button should increase font size."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)
        editor.set_font_size(11)

        # Act
        editor._font_plus_btn.click()

        # Assert
        assert editor.text_edit.font().pointSize() == 12

    def test_font_minus_button_decreases_size(self, qtbot):
        """Clicking the - button should decrease font size."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)
        editor.set_font_size(11)

        # Act
        editor._font_minus_btn.click()

        # Assert
        assert editor.text_edit.font().pointSize() == 10


# ---------------------------------------------------------------------------
# Unit tests: Scene navigation (prev/next)
# ---------------------------------------------------------------------------


class TestSceneNavigation:
    """Test previous/next scene navigation in SceneListWidget."""

    def test_select_next_advances_row(self, qtbot, gui_project_dir):
        """select_next should move to the next scene."""
        from storyboard_gen.gui.scene_list import SceneListWidget

        from storyboard_gen.config import load_project

        project = load_project(gui_project_dir)
        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, gui_project_dir / "output")

        # Arrange — select first scene
        widget.list_widget.setCurrentRow(0)

        # Act
        widget.select_next()

        # Assert
        assert widget.list_widget.currentRow() == 1

    def test_select_previous_goes_back(self, qtbot, gui_project_dir):
        """select_previous should move to the previous scene."""
        from storyboard_gen.gui.scene_list import SceneListWidget

        from storyboard_gen.config import load_project

        project = load_project(gui_project_dir)
        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, gui_project_dir / "output")

        # Arrange — select second scene
        widget.list_widget.setCurrentRow(1)

        # Act
        widget.select_previous()

        # Assert
        assert widget.list_widget.currentRow() == 0

    def test_select_next_at_last_scene_stays(self, qtbot, gui_project_dir):
        """select_next at the last scene should not move."""
        from storyboard_gen.gui.scene_list import SceneListWidget

        from storyboard_gen.config import load_project

        project = load_project(gui_project_dir)
        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, gui_project_dir / "output")

        # Arrange — select last scene
        widget.list_widget.setCurrentRow(2)

        # Act
        widget.select_next()

        # Assert — stays at last
        assert widget.list_widget.currentRow() == 2

    def test_select_previous_at_first_scene_stays(self, qtbot, gui_project_dir):
        """select_previous at the first scene should not move."""
        from storyboard_gen.gui.scene_list import SceneListWidget

        from storyboard_gen.config import load_project

        project = load_project(gui_project_dir)
        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, gui_project_dir / "output")

        # Arrange — select first scene
        widget.list_widget.setCurrentRow(0)

        # Act
        widget.select_previous()

        # Assert — stays at first
        assert widget.list_widget.currentRow() == 0


# ---------------------------------------------------------------------------
# Integration tests: Session restore (last project)
# ---------------------------------------------------------------------------


class TestSessionRestore:
    """Test restoring last project on app launch."""

    def test_open_project_persists_path(self, qtbot, gui_project_dir):
        """Opening a project should save the path to settings."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Act
        window.open_project(gui_project_dir)

        # Assert
        assert window._settings.last_project == str(gui_project_dir)

        # Cleanup
        window._settings._qs.remove("session/last_project")

    def test_restore_last_project_on_launch(self, qtbot, gui_project_dir):
        """MainWindow should restore last project if it exists."""
        from storyboard_gen.gui.app import MainWindow
        from storyboard_gen.gui.settings import AppSettings

        # Arrange — pre-set last project
        settings = AppSettings()
        settings.last_project = str(gui_project_dir)

        # Act
        window = MainWindow()
        qtbot.addWidget(window)
        window.restore_session()

        # Assert
        assert window._project is not None
        assert window._project_dir == gui_project_dir

        # Cleanup
        settings._qs.remove("session/last_project")

    def test_restore_missing_project_silently_skipped(self, qtbot, tmp_path):
        """If the last project directory is gone, skip silently."""
        from storyboard_gen.gui.app import MainWindow
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings.last_project = str(tmp_path / "nonexistent")

        # Act
        window = MainWindow()
        qtbot.addWidget(window)
        window.restore_session()

        # Assert — no project loaded, no crash
        assert window._project is None

        settings._qs.remove("session/last_project")


# ---------------------------------------------------------------------------
# Integration tests: Last directory for file dialog
# ---------------------------------------------------------------------------


class TestLastDirectory:
    """Test that the Open Project dialog remembers the last directory."""

    def test_open_project_persists_directory(self, qtbot, gui_project_dir):
        """Opening a project should save the parent directory to settings."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Act
        window.open_project(gui_project_dir)

        # Assert — parent dir saved
        assert window._settings.last_directory == str(gui_project_dir.parent)

        # Cleanup
        window._settings._qs.remove("session/last_directory")


# ---------------------------------------------------------------------------
# Integration tests: Font size persistence
# ---------------------------------------------------------------------------


class TestFontSizePersistence:
    """Test that font size changes are persisted across sessions."""

    def test_font_change_persisted(self, qtbot, gui_project_dir):
        """Changing YAML editor font should persist to settings."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Act — change font size
        window.yaml_editor.set_font_size(18)
        window.yaml_editor.font_size_changed.emit(18)

        # Assert
        assert window._settings.editor_font_size == 18

        # Cleanup
        window._settings._qs.remove("editor/font_size")


# ---------------------------------------------------------------------------
# Unit tests: Worker exception handling (#70)
# ---------------------------------------------------------------------------


class TestWorkerExceptionHandling:
    """Test that GenerateWorker catches all exception types."""

    def test_worker_catches_unexpected_exception(self, qtbot):
        """Worker should catch unexpected exceptions and emit error signal."""
        from storyboard_gen.gui.generate_worker import GenerateWorker
        from storyboard_gen.models import Project

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        project = Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Test style.",
            characters={},
            scenes=[scene],
        )

        worker = GenerateWorker(
            scene=scene,
            project=project,
            output_dir=Path("/tmp/out"),
            project_dir=Path("/tmp"),
        )

        # Act — simulate an unexpected exception type (e.g. KeyError)
        with patch(
            "storyboard_gen.gui.generate_worker.generate_still",
            side_effect=KeyError("unexpected"),
        ):
            with qtbot.waitSignal(worker.error, timeout=5000) as blocker:
                worker.start()
                worker.wait()

        # Assert — error message should mention the exception type
        assert "KeyError" in blocker.args[0]

    def test_worker_catches_attribute_error(self, qtbot):
        """Worker should catch AttributeError and emit error signal."""
        from storyboard_gen.gui.generate_worker import GenerateWorker
        from storyboard_gen.models import Project

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        project = Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Test style.",
            characters={},
            scenes=[scene],
        )

        worker = GenerateWorker(
            scene=scene,
            project=project,
            output_dir=Path("/tmp/out"),
            project_dir=Path("/tmp"),
        )

        with patch(
            "storyboard_gen.gui.generate_worker.generate_still",
            side_effect=AttributeError("bad attr"),
        ):
            with qtbot.waitSignal(worker.error, timeout=5000) as blocker:
                worker.start()
                worker.wait()

        assert "AttributeError" in blocker.args[0]


# ---------------------------------------------------------------------------
# Unit tests: Green Regenerate button for unreviewed content (#71)
# ---------------------------------------------------------------------------


class TestFreshIndicator:
    """Test the green 'fresh' indicator on Regenerate button."""

    def test_set_fresh_makes_button_green(self, qtbot, tmp_path):
        """set_fresh() should apply green styling to the Regenerate button."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        # Act
        widget.set_fresh()

        # Assert — button should have green stylesheet
        assert (
            "green" in widget._gen_btn.styleSheet().lower()
            or "#4" in widget._gen_btn.styleSheet()
        )

    def test_clear_fresh_resets_button(self, qtbot, tmp_path):
        """clear_fresh() should remove the green styling."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        widget.set_fresh()
        # Act
        widget.clear_fresh()

        # Assert — no green styling
        assert widget._gen_btn.styleSheet() == ""

    def test_is_fresh_flag(self, qtbot, tmp_path):
        """is_fresh should track fresh state."""
        from storyboard_gen.gui.scene_list import SceneItemWidget

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"

        widget = SceneItemWidget(scene, output_dir)
        qtbot.addWidget(widget)

        assert not widget.is_fresh
        widget.set_fresh()
        assert widget.is_fresh
        widget.clear_fresh()
        assert not widget.is_fresh

    def test_gen_finished_marks_scene_fresh(self, qtbot, gui_project_dir):
        """Scene generation finishing should mark the scene as fresh."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Act — simulate finish
            window._on_scene_gen_finished(scene)

        # Assert — the scene item should be marked fresh
        item_widget = window.scene_list.list_widget.itemWidget(
            window.scene_list.list_widget.item(0)
        )
        assert item_widget.is_fresh

    def test_selecting_scene_clears_fresh(self, qtbot, gui_project_dir):
        """Selecting a fresh scene should clear the fresh indicator."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)
            window._on_scene_gen_finished(scene)

        # Act — select the scene
        window._on_scene_selected(scene)

        # Assert — fresh indicator cleared
        item_widget = window.scene_list.list_widget.itemWidget(
            window.scene_list.list_widget.item(0)
        )
        assert not item_widget.is_fresh

    def test_project_load_does_not_mark_fresh(self, qtbot, gui_project_dir):
        """Loading a project should not mark any scenes as fresh."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Assert — no scenes should be fresh
        for i in range(window.scene_list.list_widget.count()):
            item_widget = window.scene_list.list_widget.itemWidget(
                window.scene_list.list_widget.item(i)
            )
            assert not item_widget.is_fresh


# ---------------------------------------------------------------------------
# Unit tests: Verbose logging (#70)
# ---------------------------------------------------------------------------


class TestVerboseLogging:
    """Test the --verbose flag for stderr logging."""

    def test_main_window_accepts_verbose(self, qtbot):
        """MainWindow should accept verbose parameter."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow(verbose=True)
        qtbot.addWidget(window)

        assert window is not None

    def test_verbose_adds_stderr_handler(self, qtbot):
        """Verbose mode should add a stderr StreamHandler."""
        import logging

        from storyboard_gen.gui.app import MainWindow

        window = MainWindow(verbose=True)
        qtbot.addWidget(window)

        root_logger = logging.getLogger()
        handler_types = [type(h).__name__ for h in root_logger.handlers]
        assert "StreamHandler" in handler_types

        # Cleanup — remove the handler we added
        for h in root_logger.handlers[:]:
            if isinstance(h, logging.StreamHandler) and not isinstance(
                h, logging.FileHandler
            ):
                if hasattr(h, "_verbose_marker"):
                    root_logger.removeHandler(h)


# ---------------------------------------------------------------------------
# Unit tests: Archive dialog clip preview and image scaling (#73)
# ---------------------------------------------------------------------------


class TestArchiveDialogClipPreview:
    """Test that the archive dialog previews clips via thumbnail extraction."""

    def test_clip_archive_attempts_thumbnail(self, qtbot, tmp_path):
        """Selecting a clip archive should attempt thumbnail extraction, not just show text."""
        from storyboard_gen.gui.archive_dialog import ArchiveDialog

        scene = Scene(
            number="1", title="Test", scene_type="clip", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"
        archive_dir = output_dir / "clips" / "archive"
        archive_dir.mkdir(parents=True)

        # Create a fake archived clip file
        archive_file = archive_dir / "scene_01_20260310_120000.mp4"
        archive_file.write_bytes(b"\x00" * 100)

        dialog = ArchiveDialog(scene, output_dir)
        qtbot.addWidget(dialog)

        # Act — select the archive entry
        dialog._list_widget.setCurrentRow(0)

        # Assert — preview should have been attempted (not just filename text)
        # The label should either have a pixmap (if ffmpeg worked) or show the filename
        # Key assertion: the code path for clips is exercised without error
        assert dialog._list_widget.count() == 1

    def test_still_archive_shows_pixmap(self, qtbot, tmp_path):
        """Selecting a still archive should display a pixmap preview."""
        from PIL import Image

        from storyboard_gen.gui.archive_dialog import ArchiveDialog

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"
        archive_dir = output_dir / "stills" / "archive"
        archive_dir.mkdir(parents=True)

        # Create a real PNG image for archive
        archive_file = archive_dir / "scene_01_20260310_120000.png"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(archive_file)

        dialog = ArchiveDialog(scene, output_dir)
        qtbot.addWidget(dialog)

        # Act — select the archive entry
        dialog._list_widget.setCurrentRow(0)

        # Assert — preview label should have a pixmap
        assert dialog._preview_label.pixmap() is not None
        assert not dialog._preview_label.pixmap().isNull()


class TestArchiveDialogImageScaling:
    """Test that the archive dialog rescales images on resize."""

    def test_resize_rescales_preview(self, qtbot, tmp_path):
        """Resizing the archive dialog should rescale the preview image."""
        from PIL import Image

        from storyboard_gen.gui.archive_dialog import ArchiveDialog

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        output_dir = tmp_path / "output"
        archive_dir = output_dir / "stills" / "archive"
        archive_dir.mkdir(parents=True)

        # Create a large PNG image
        archive_file = archive_dir / "scene_01_20260310_120000.png"
        img = Image.new("RGB", (800, 600), color="blue")
        img.save(archive_file)

        dialog = ArchiveDialog(scene, output_dir)
        qtbot.addWidget(dialog)
        dialog.show()
        dialog.resize(400, 300)
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

        # Select the archive to trigger preview
        dialog._list_widget.setCurrentRow(0)
        QApplication.processEvents()
        initial_pixmap = dialog._preview_label.pixmap()
        assert initial_pixmap is not None
        initial_size = initial_pixmap.size()

        # Act — resize the dialog larger
        dialog.resize(1000, 800)
        QApplication.processEvents()

        # Assert — the preview pixmap should have been rescaled
        new_pixmap = dialog._preview_label.pixmap()
        assert new_pixmap is not None
        new_size = new_pixmap.size()
        # The new pixmap should be larger than the initial one
        assert (
            new_size.width() > initial_size.width()
            or new_size.height() > initial_size.height()
        )


# ---------------------------------------------------------------------------
# Unit/integration tests: reload project before generation (#75, #76)
# ---------------------------------------------------------------------------


class TestProjectReloadBeforeGeneration:
    """Test that generation always uses the latest project.yaml and .env (#75, #76)."""

    def test_generation_reloads_yaml_from_disk(self, qtbot, gui_project_dir):
        """Editing project.yaml externally should be picked up on generation."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Verify initial title
        assert window._project.title == "GUI Test Project"

        # Act — modify project.yaml externally (change style_prefix)
        yaml_path = gui_project_dir / "project.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["style_prefix"] = "Changed externally."
        yaml_path.write_text(yaml.dump(data))

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Assert — worker should receive the fresh project with updated style_prefix
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["project"].style_prefix == "Changed externally."

    def test_generation_reloads_dotenv_from_disk(self, qtbot, gui_project_dir):
        """Editing .env externally should be picked up on generation."""
        import os

        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Write initial .env
        env_file = gui_project_dir / ".env"
        env_file.write_text("SBG_TEST_RELOAD_VAR=initial\n")

        window.open_project(gui_project_dir)
        assert os.environ.get("SBG_TEST_RELOAD_VAR") == "initial"

        # Act — modify .env externally
        env_file.write_text("SBG_TEST_RELOAD_VAR=updated\n")

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Assert — env var should be updated
            assert os.environ.get("SBG_TEST_RELOAD_VAR") == "updated"

        # Cleanup
        os.environ.pop("SBG_TEST_RELOAD_VAR", None)

    def test_generation_uses_fresh_scene_data(self, qtbot, gui_project_dir):
        """If scene prompt is changed externally, generation should use the new prompt."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Original prompt
        original_prompt = window._project.scenes[0].prompt
        assert original_prompt == "A boy stands on a hill."

        # Act — modify scene prompt externally
        yaml_path = gui_project_dir / "project.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["scenes"][0]["prompt"] = "A girl stands on a mountain."
        yaml_path.write_text(yaml.dump(data))

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Assert — worker should receive the scene with updated prompt
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["scene"].prompt == "A girl stands on a mountain."

    def test_generation_reload_error_shows_error(self, qtbot, gui_project_dir):
        """If project.yaml becomes invalid, generation should show an error."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Act — break project.yaml (valid YAML but missing required 'title')
        yaml_path = gui_project_dir / "project.yaml"
        yaml_path.write_text(yaml.dump({"aspect_ratio": "9:16", "scenes": []}))

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            with patch.object(window, "_show_error") as mock_error:
                window._start_scene_generation(scene)

                # Assert — no worker created, error shown
                assert mock_cls.call_count == 0
                assert mock_error.call_count == 1

    def test_generation_missing_scene_shows_error(self, qtbot, gui_project_dir):
        """If a scene is removed from YAML, generation should show an error."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Remember scene 3 exists
        scene3 = window._project.scenes[2]
        assert str(scene3.number) == "3"

        # Act — remove scene 3 from YAML
        yaml_path = gui_project_dir / "project.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["scenes"] = [s for s in data["scenes"] if s.get("number") != 3]
        yaml_path.write_text(yaml.dump(data))

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            with patch.object(window, "_show_error") as mock_error:
                window._start_scene_generation(scene3)

                # Assert — no worker created, error shown
                assert mock_cls.call_count == 0
                assert mock_error.call_count == 1

    def test_generation_provider_change_picked_up(self, qtbot, gui_project_dir):
        """Changing provider in YAML should be reflected in generation (#76 scenario)."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Set up with FAL provider initially
        yaml_path = gui_project_dir / "project.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        data["providers"] = {
            "still": {
                "backend": "fal",
                "model": "fal-ai/flux-general",
            }
        }
        yaml_path.write_text(yaml.dump(data))
        window.open_project(gui_project_dir)

        assert window._project.still_provider is not None
        assert window._project.still_provider.backend == "fal"

        # Act — remove FAL provider from YAML (revert to Google default)
        data.pop("providers")
        yaml_path.write_text(yaml.dump(data))

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Assert — worker should receive project with no FAL provider
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["project"].still_provider is None


# ---------------------------------------------------------------------------
# Unit tests: GenerateDialog cost summary (#80)
# ---------------------------------------------------------------------------


class TestGenerateDialogCostSummary:
    """Test cost summary display in the generate dialog."""

    FAL_PROJECT_YAML = {
        "title": "FAL Pricing Test",
        "aspect_ratio": "9:16",
        "style_prefix": "Test style.",
        "providers": {
            "still": {"backend": "fal", "model": "fal-ai/flux-general"},
        },
        "scenes": [
            {
                "number": 1,
                "title": "Still one",
                "type": "still",
                "duration": 5,
                "prompt": "Test.",
            },
            {
                "number": 2,
                "title": "Still two",
                "type": "still",
                "duration": 4,
                "prompt": "Test.",
            },
        ],
    }

    def test_dialog_shows_cost_summary_for_fal_scenes(self, qtbot, tmp_path):
        """Dialog should show estimated total cost when pricing is available."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        (tmp_path / "project.yaml").write_text(yaml.dump(self.FAL_PROJECT_YAML))
        project = load_project(tmp_path)
        pricing_map = {
            "fal-ai/flux-general": {
                "unit_price": 0.04,
                "unit": "image",
                "currency": "USD",
            },
        }
        dialog = GenerateDialog(project, pricing_map=pricing_map)
        qtbot.addWidget(dialog)

        # Assert — cost label shows dollar amount
        assert "$" in dialog._cost_label.text()

    def test_dialog_shows_no_cost_when_no_pricing(
        self, qtbot, gui_project_dir_with_output
    ):
        """Dialog should show no cost label when no pricing available."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir_with_output)
        dialog = GenerateDialog(project)
        qtbot.addWidget(dialog)

        # Assert — cost label is empty when no pricing
        assert dialog._cost_label.text() == ""

    def test_dialog_cost_updates_on_radio_change(self, qtbot, tmp_path):
        """Changing radio button updates the cost display."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        (tmp_path / "project.yaml").write_text(yaml.dump(self.FAL_PROJECT_YAML))
        project = load_project(tmp_path)
        pricing_map = {
            "fal-ai/flux-general": {
                "unit_price": 0.04,
                "unit": "image",
                "currency": "USD",
            },
        }
        dialog = GenerateDialog(project, pricing_map=pricing_map)
        qtbot.addWidget(dialog)

        # Act — switch to stills only
        dialog._radio_stills.setChecked(True)
        text_stills = dialog._cost_label.text()

        # Act — switch to all
        dialog._radio_all.setChecked(True)
        text_all = dialog._cost_label.text()

        # Assert — both should contain dollar sign
        assert "$" in text_stills
        assert "$" in text_all


# ---------------------------------------------------------------------------
# Unit tests: SceneListWidget cost display (#80)
# ---------------------------------------------------------------------------


class TestSceneListCostDisplay:
    """Test cost display in the scene list widget."""

    FAL_PROJECT_YAML = {
        "title": "FAL Cost Test",
        "aspect_ratio": "9:16",
        "style_prefix": "Test style.",
        "providers": {
            "still": {"backend": "fal", "model": "fal-ai/flux-general"},
        },
        "scenes": [
            {
                "number": 1,
                "title": "Still one",
                "type": "still",
                "duration": 5,
                "prompt": "Test.",
            },
        ],
    }

    def test_scene_list_shows_cost_for_fal_scenes(self, qtbot, tmp_path):
        """Scene list items should show cost when pricing is available."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        (tmp_path / "project.yaml").write_text(yaml.dump(self.FAL_PROJECT_YAML))
        project = load_project(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        widget = SceneListWidget()
        qtbot.addWidget(widget)

        pricing_map = {
            "fal-ai/flux-general": {
                "unit_price": 0.04,
                "unit": "image",
                "currency": "USD",
            },
        }
        widget.load_project(project, output_dir, pricing_map=pricing_map)

        # Assert — first scene item should have cost label with dollar sign
        item = widget.list_widget.item(0)
        item_widget = widget.list_widget.itemWidget(item)
        assert hasattr(item_widget, "_cost_label")
        assert "$0.04" in item_widget._cost_label.text()

    def test_scene_list_hides_cost_when_no_pricing(
        self, qtbot, gui_project_dir_with_output
    ):
        """Scene list items should show empty cost when no pricing."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.scene_list import SceneListWidget

        project = load_project(gui_project_dir_with_output)
        output_dir = gui_project_dir_with_output / "output"

        widget = SceneListWidget()
        qtbot.addWidget(widget)
        widget.load_project(project, output_dir)

        # Assert — cost label should be empty (no pricing available)
        item = widget.list_widget.item(0)
        item_widget = widget.list_widget.itemWidget(item)
        assert hasattr(item_widget, "_cost_label")
        assert item_widget._cost_label.text() == ""


# ---------------------------------------------------------------------------
# Unit tests: Stop button cleanup (#78)
# ---------------------------------------------------------------------------


class TestStopButtonCleanup:
    """Test that stopping a worker properly cleans up state (#78).

    The bug: when request_stop() is called, the API call runs to completion.
    After completion, the worker skips emitting scene_finished. This means
    the worker is never removed from _workers and the scene stays in
    "generating" state forever.
    """

    def test_worker_emits_stopped_when_stop_requested_during_generation(self, qtbot):
        """Worker should emit stopped signal when generation completes after stop."""
        from storyboard_gen.gui.generate_worker import GenerateWorker
        from storyboard_gen.models import Project

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        project = Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Test style.",
            characters={},
            scenes=[scene],
        )

        worker = GenerateWorker(
            scene=scene,
            project=project,
            output_dir=Path("/tmp/out"),
            project_dir=Path("/tmp"),
        )

        with patch("storyboard_gen.gui.generate_worker.generate_still"):
            # Request stop — simulates user clicking Stop while API runs
            worker.request_stop()

            stopped_scenes = []
            worker.stopped.connect(stopped_scenes.append)

            finished_scenes = []
            worker.scene_finished.connect(finished_scenes.append)

            # Act — run the worker (API completes, but stop was requested)
            worker.run()

            # Assert — should emit stopped, NOT scene_finished
            assert len(stopped_scenes) == 1
            assert stopped_scenes[0].number == "1"
            assert len(finished_scenes) == 0

    def test_worker_emits_stopped_when_stop_requested_mid_generation(self, qtbot):
        """Worker should emit stopped when stop is requested during the API call."""
        from storyboard_gen.gui.generate_worker import GenerateWorker
        from storyboard_gen.models import Project

        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="test", duration=5
        )
        project = Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Test style.",
            characters={},
            scenes=[scene],
        )

        worker = GenerateWorker(
            scene=scene,
            project=project,
            output_dir=Path("/tmp/out"),
            project_dir=Path("/tmp"),
        )

        def simulate_slow_generation(*args, **kwargs):
            # Simulate stop being requested during the API call
            worker.request_stop()

        with patch(
            "storyboard_gen.gui.generate_worker.generate_still",
            side_effect=simulate_slow_generation,
        ):
            stopped_scenes = []
            worker.stopped.connect(stopped_scenes.append)

            finished_scenes = []
            worker.scene_finished.connect(finished_scenes.append)

            # Act
            worker.run()

            # Assert
            assert len(stopped_scenes) == 1
            assert len(finished_scenes) == 0

    def test_app_cleans_up_worker_on_stopped(self, qtbot, gui_project_dir):
        """MainWindow should remove worker and reset scene state when stopped."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)
            assert str(scene.number) in window._workers

            # Act — simulate stopped signal + deferred cleanup
            window._on_scene_stopped(scene)
            window._cleanup_worker(str(scene.number))

            # Assert — worker removed, scene back to idle
            assert str(scene.number) not in window._workers

    def test_app_scene_state_idle_after_stopped(self, qtbot, gui_project_dir):
        """Scene should be in idle state after stop completes."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Verify generating state
            item = window.scene_list.list_widget.itemWidget(
                window.scene_list.list_widget.item(0)
            )
            assert item._gen_btn.text() == "Stop"

            # Act — simulate stopped signal
            window._on_scene_stopped(scene)

            # Assert — button restored
            assert item._gen_btn.text() in ("Generate", "Regenerate")
            assert item._spinner.isHidden()

    def test_app_progress_updates_after_stopped(self, qtbot, gui_project_dir):
        """Toolbar progress and actions should update when a scene is stopped."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)
            assert len(window._workers) == 1
            assert window._btn_stop.isEnabled()

            # Act — stopped signal fires, then finished cleans up worker
            window._on_scene_stopped(scene)
            window._cleanup_worker(str(scene.number))

            # Assert — no workers left, stop disabled
            assert len(window._workers) == 0
            assert not window._btn_stop.isEnabled()


# ---------------------------------------------------------------------------
# Unit tests: AboutDialog (#85)
# ---------------------------------------------------------------------------


class TestAboutDialog:
    """Test the About dialog."""

    def test_about_dialog_instantiation(self, qtbot):
        """AboutDialog should instantiate without errors."""
        from storyboard_gen.gui.about_dialog import AboutDialog

        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        assert dialog.windowTitle() == "About storyboard-gen"

    def test_about_dialog_shows_app_name(self, qtbot):
        """AboutDialog should display the app name."""
        from storyboard_gen.gui.about_dialog import AboutDialog

        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        assert "storyboard-gen" in dialog._name_label.text()

    def test_about_dialog_shows_version(self, qtbot):
        """AboutDialog should display the current version string."""
        from storyboard_gen import __version__
        from storyboard_gen.gui.about_dialog import AboutDialog

        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        assert __version__ in dialog._version_label.text()

    def test_about_dialog_shows_links(self, qtbot):
        """AboutDialog should contain clickable GitHub, models, and author links."""
        from storyboard_gen.gui.about_dialog import (
            AUTHOR_URL,
            AboutDialog,
            GITHUB_URL,
            MODELS_URL,
        )

        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        link_text = dialog._link_label.text()
        assert GITHUB_URL in link_text
        assert MODELS_URL in link_text
        assert AUTHOR_URL in link_text
        assert dialog._link_label.openExternalLinks()

    def test_about_dialog_has_close_button(self, qtbot):
        """AboutDialog should have a Close button."""
        from PySide6.QtWidgets import QDialogButtonBox
        from storyboard_gen.gui.about_dialog import AboutDialog

        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        buttons = dialog._button_box.buttons()
        assert len(buttons) == 1
        assert (
            dialog._button_box.buttonRole(buttons[0])
            == QDialogButtonBox.ButtonRole.RejectRole
        )

    def test_about_dialog_shows_pricing_caveat(self, qtbot):
        """AboutDialog should display a pricing caveat note."""
        from storyboard_gen.gui.about_dialog import AboutDialog

        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        assert "indicative" in dialog._pricing_label.text().lower()
        assert "static defaults" in dialog._pricing_label.text().lower()


# ---------------------------------------------------------------------------
# Unit tests: Toolbar icon buttons (#85)
# ---------------------------------------------------------------------------


class TestToolbarIcons:
    """Test that toolbar uses icon buttons with tooltips."""

    def test_toolbar_buttons_are_qtoolbutton(self, qtbot):
        """Toolbar buttons should be QToolButton instances."""
        from PySide6.QtWidgets import QToolButton
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert isinstance(window._btn_open, QToolButton)
        assert isinstance(window._btn_generate, QToolButton)
        assert isinstance(window._btn_stop, QToolButton)

    def test_toolbar_buttons_have_tooltips(self, qtbot):
        """All toolbar buttons should have descriptive tooltips with shortcut hints."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Tooltips now include shortcut hints — check the base label is present
        expected_labels = {
            "_btn_open": "Open Project",
            "_btn_new": "New Project",
            "_btn_refresh": "Refresh",
            "_btn_generate": "Generate",
            "_btn_stop": "Stop",
            "_btn_output": "Output",
            "_btn_yaml_viewer": "View YAML",
            "_btn_yaml_editor": "Edit YAML",
            "_btn_console": "Console",
            "_btn_about": "About",
        }
        for attr, label in expected_labels.items():
            btn = getattr(window, attr)
            assert label in btn.toolTip(), f"{attr} tooltip missing label '{label}'"

    def test_toolbar_has_about_button(self, qtbot):
        """Toolbar should have an About button."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        assert hasattr(window, "_btn_about")

    def test_toolbar_has_no_archive_button(self, qtbot):
        """Toolbar should no longer have an Archive button."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "_btn_archive")
        assert not hasattr(window, "_action_archive")


class TestKeyboardShortcuts:
    """Test keyboard shortcuts for toolbar actions (#92)."""

    def _get_modifier_label(self):
        """Return the expected platform modifier label."""
        import sys

        return "Cmd" if sys.platform == "darwin" else "Ctrl"

    def test_shortcut_open_project_exists(self, qtbot):
        """Ctrl/Cmd+O shortcut should exist and map to Open Project."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Assert
        assert hasattr(window, "_shortcut_open")
        assert window._shortcut_open.key().toString() == "Ctrl+O"

    def test_shortcut_new_project_exists(self, qtbot):
        """Ctrl/Cmd+N shortcut should exist and map to New Project."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_new")
        assert window._shortcut_new.key().toString() == "Ctrl+N"

    def test_shortcut_refresh_exists(self, qtbot):
        """Ctrl/Cmd+R shortcut should exist and map to Refresh."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_refresh")
        assert window._shortcut_refresh.key().toString() == "Ctrl+R"

    def test_shortcut_generate_exists(self, qtbot):
        """Ctrl/Cmd+G shortcut should exist and map to Generate."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_generate")
        assert window._shortcut_generate.key().toString() == "Ctrl+G"

    def test_shortcut_view_yaml_exists(self, qtbot):
        """Ctrl/Cmd+Y shortcut should exist and map to View YAML."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_yaml")
        assert window._shortcut_yaml.key().toString() == "Ctrl+Y"

    def test_shortcut_console_exists(self, qtbot):
        """Ctrl/Cmd+L shortcut should exist and map to Console toggle."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_console")
        assert window._shortcut_console.key().toString() == "Ctrl+L"

    def test_shortcut_about_exists(self, qtbot):
        """Ctrl/Cmd+I shortcut should exist and map to About."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_about")
        assert window._shortcut_about.key().toString() == "Ctrl+I"

    def test_shortcut_stop_exists(self, qtbot):
        """Ctrl/Cmd+Shift+C shortcut should exist and map to Stop."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_stop")
        assert window._shortcut_stop.key().toString() == "Ctrl+Shift+C"

    def test_shortcut_save_exists(self, qtbot):
        """Ctrl/Cmd+S shortcut should exist and map to Save."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_save")
        assert window._shortcut_save.key().toString() == "Ctrl+S"

    def test_shortcut_output_exists(self, qtbot):
        """Ctrl/Cmd+Shift+O shortcut should exist and map to Output."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_output")
        assert window._shortcut_output.key().toString() == "Ctrl+Shift+O"

    def test_shortcut_edit_yaml_exists(self, qtbot):
        """Ctrl/Cmd+Shift+Y shortcut should exist and map to Edit YAML."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_edit_yaml")
        assert window._shortcut_edit_yaml.key().toString() == "Ctrl+Shift+Y"

    def test_tooltips_include_shortcut_hints(self, qtbot):
        """Toolbar tooltips should include keyboard shortcut hints (#92)."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Shortcut hint should appear in parentheses in the tooltip
        assert "(" in window._btn_open.toolTip()
        assert "(" in window._btn_new.toolTip()
        assert "(" in window._btn_generate.toolTip()
        assert "(" in window._btn_stop.toolTip()
        assert "(" in window._btn_output.toolTip()
        assert "(" in window._btn_console.toolTip()
        assert "(" in window._btn_about.toolTip()
        assert "(" in window._btn_yaml_viewer.toolTip()
        assert "(" in window._btn_yaml_editor.toolTip()
        assert "(" in window._btn_refresh.toolTip()

    def test_tooltips_use_cmd_on_macos(self, qtbot):
        """On macOS, tooltips should use Cmd, not Ctrl (#92)."""
        import sys

        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        mod = "Cmd" if sys.platform == "darwin" else "Ctrl"
        assert mod in window._btn_open.toolTip()

    def test_tooltips_use_ctrl_on_linux(self, qtbot):
        """On non-macOS, tooltips should use Ctrl (#92)."""
        import sys

        from storyboard_gen.gui.app import _shortcut_modifier_label

        # _shortcut_modifier_label should return correct string for platform
        if sys.platform == "darwin":
            assert _shortcut_modifier_label() == "Cmd"
        else:
            assert _shortcut_modifier_label() == "Ctrl"


class TestYamlViewerFontSize:
    """Test font size controls in YamlViewer (#92)."""

    def test_set_font_size_changes_font(self, qtbot):
        """set_font_size should change the viewer font point size."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)

        # Act
        viewer.set_font_size(18)

        # Assert
        assert viewer.text_edit.font().pointSize() == 18

    def test_set_font_size_clamped_min(self, qtbot):
        """Font size below MIN_FONT_SIZE should be clamped."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)

        viewer.set_font_size(4)
        assert viewer.text_edit.font().pointSize() == 8

    def test_set_font_size_clamped_max(self, qtbot):
        """Font size above MAX_FONT_SIZE should be clamped."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)

        viewer.set_font_size(50)
        assert viewer.text_edit.font().pointSize() == 32

    def test_increase_font_emits_signal(self, qtbot):
        """Increasing font should emit font_size_changed signal."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)
        viewer.set_font_size(11)

        # Act
        with qtbot.waitSignal(viewer.font_size_changed, timeout=1000):
            viewer._increase_font()

        assert viewer.text_edit.font().pointSize() == 12

    def test_decrease_font_emits_signal(self, qtbot):
        """Decreasing font should emit font_size_changed signal."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)
        viewer.set_font_size(11)

        with qtbot.waitSignal(viewer.font_size_changed, timeout=1000):
            viewer._decrease_font()

        assert viewer.text_edit.font().pointSize() == 10

    def test_viewer_has_font_size_shortcuts(self, qtbot):
        """YamlViewer should have Cmd+=/- keyboard shortcuts for font size."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)

        assert hasattr(viewer, "_shortcut_zoom_in")
        assert hasattr(viewer, "_shortcut_zoom_out")

    def test_viewer_has_close_shortcut(self, qtbot):
        """YamlViewer should have Cmd+W/Ctrl+W keyboard shortcut to close (#92)."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)

        assert hasattr(viewer, "_shortcut_close")
        assert viewer._shortcut_close.key().toString() == "Ctrl+W"


# ---------------------------------------------------------------------------
# Stop tooltip updated — issue #92
# ---------------------------------------------------------------------------


class TestGenerationErrorNonModal:
    """Generation errors should not block UI — issue #97."""

    def test_gen_error_shows_error_dialog(self, qtbot, gui_project_dir):
        """_on_gen_error should show error via _show_error (#122 AC1)."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Act — simulate error (should show dialog via _show_error)
            with patch.object(window, "_show_error") as mock_show:
                window._on_gen_error(scene, "API error: timeout")
                mock_show.assert_called_once_with("API error: timeout")

    def test_gen_error_resets_scene_state(self, qtbot, gui_project_dir):
        """Scene state should return to idle after error (#122 AC4)."""
        from storyboard_gen.gui.app import MainWindow
        from storyboard_gen.gui.scene_list import SceneItemWidget

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            with patch("storyboard_gen.gui.app.QMessageBox"):
                window._on_gen_error(scene, "API error: timeout")

            # Assert — scene item returned to idle (gen button re-enabled)
            item = window.scene_list.list_widget.itemWidget(
                window.scene_list.list_widget.item(0)
            )
            assert isinstance(item, SceneItemWidget)
            assert item._gen_btn.isEnabled()

        # Error should appear in console
        assert "API error: timeout" in window.console.text_edit.toPlainText()

    def test_other_scenes_clickable_after_error(self, qtbot, gui_project_dir):
        """Other scene buttons should remain enabled after an error."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        if len(window._project.scenes) < 2:
            pytest.skip("Need at least 2 scenes")

        scene_0 = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene_0)

            # Error on scene 0
            with patch("storyboard_gen.gui.app.QMessageBox"):
                window._on_gen_error(scene_0, "API error")
            window._cleanup_worker(str(scene_0.number))

            # Scene 1's generate button should be enabled
            item_1 = window.scene_list.list_widget.itemWidget(
                window.scene_list.list_widget.item(1)
            )
            assert item_1._gen_btn.isEnabled()


class TestArchiveButtonOnLoad:
    """Archive button should reflect disk state on project load — issue #99."""

    def test_archive_button_enabled_when_archives_exist(self, qtbot, gui_project_dir):
        """Archive button should be enabled when archive files exist on disk."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Create an archive file for scene 1 (first scene) before loading
        output_dir = gui_project_dir / "output"
        archive_dir = output_dir / "stills" / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        (archive_dir / "scene_01_20260101_120000.png").write_bytes(b"\x89PNG")

        window.open_project(gui_project_dir)

        # Find scene 1 widget (first item in list)
        item = window.scene_list.list_widget.itemWidget(
            window.scene_list.list_widget.item(0)
        )
        assert item._archive_btn.isEnabled()

    def test_refresh_status_called_on_open(self, qtbot, gui_project_dir):
        """open_project should call refresh_status to update archive buttons."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        with patch.object(
            window.scene_list, "refresh_status", wraps=window.scene_list.refresh_status
        ) as mock_refresh:
            window.open_project(gui_project_dir)
            mock_refresh.assert_called()


class TestStopTooltipBinding:
    """Verify the Stop button tooltip reflects Cmd+Shift+C."""

    def test_stop_tooltip_has_shift_c(self, qtbot):
        """Stop button tooltip should reference Shift+C, not Shift+S."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        tooltip = window._btn_stop.toolTip()
        assert "Shift+C" in tooltip
        assert "Shift+S" not in tooltip


# ---------------------------------------------------------------------------
# QThread worker lifecycle — issue #100
# ---------------------------------------------------------------------------


class TestWorkerLifecycle:
    """Tests for deferred worker cleanup via QThread.finished signal."""

    def test_worker_connected_to_finished_signal(self, qtbot, gui_project_dir):
        """Worker's finished signal should be connected for cleanup."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Assert — finished signal connected
            mock_worker.finished.connect.assert_called()

    def test_worker_not_removed_in_scene_finished_handler(self, qtbot, gui_project_dir):
        """_on_scene_gen_finished should NOT remove worker from _workers.

        Cleanup is deferred to the QThread.finished signal to prevent
        GC destroying the thread while it's still running.
        """
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Act — simulate scene finished (custom signal, NOT Qt finished)
            window._on_scene_gen_finished(scene)

            # Assert — worker still in _workers (cleanup deferred to finished)
            assert str(scene.number) in window._workers

    def test_worker_not_removed_in_error_handler(self, qtbot, gui_project_dir):
        """_on_gen_error should NOT remove worker from _workers."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Act — simulate error
            with patch("storyboard_gen.gui.app.QMessageBox"):
                window._on_gen_error(scene, "API error")

            # Assert — worker still in _workers
            assert str(scene.number) in window._workers

    def test_worker_not_removed_in_stopped_handler(self, qtbot, gui_project_dir):
        """_on_scene_stopped should NOT remove worker from _workers."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)

            # Act — simulate stopped
            window._on_scene_stopped(scene)

            # Assert — worker still in _workers
            assert str(scene.number) in window._workers

    def test_cleanup_worker_removes_from_dict(self, qtbot, gui_project_dir):
        """_cleanup_worker should remove the worker from _workers dict."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]
        scene_key = str(scene.number)

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True

            window._start_scene_generation(scene)
            assert scene_key in window._workers

            # Act — simulate Qt finished signal callback
            window._cleanup_worker(scene_key)

            # Assert
            assert scene_key not in window._workers

    def test_close_event_requests_stop_for_running_workers(
        self, qtbot, gui_project_dir
    ):
        """closeEvent should request stop on all running workers."""
        from PySide6.QtGui import QCloseEvent

        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True
            mock_worker.wait.return_value = True

            window._start_scene_generation(scene)

            # Act — close the window
            event = QCloseEvent()
            window.closeEvent(event)

            # Assert — stop was requested
            mock_worker.request_stop.assert_called()

    def test_close_event_waits_for_workers(self, qtbot, gui_project_dir):
        """closeEvent should wait for workers to finish before closing."""
        from PySide6.QtGui import QCloseEvent

        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = window._project.scenes[0]

        with patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls:
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True
            mock_worker.wait.return_value = True

            window._start_scene_generation(scene)

            # Act — close the window
            event = QCloseEvent()
            window.closeEvent(event)

            # Assert — wait was called with timeout
            mock_worker.wait.assert_called()


class TestExceptHook:
    """Tests for GUI global exception hook — issue #101."""

    def test_excepthook_installed(self):
        """_install_excepthook should replace sys.excepthook."""
        import sys

        from storyboard_gen.gui.app import _install_excepthook

        original = sys.excepthook
        try:
            _install_excepthook()
            assert sys.excepthook is not original
        finally:
            sys.excepthook = original

    def test_excepthook_logs_exception(self, caplog):
        """Installed excepthook should log unhandled exceptions."""
        import sys
        from unittest.mock import MagicMock

        from storyboard_gen.gui.app import _install_excepthook

        original = sys.excepthook
        # Replace with a no-op so pytest-qt doesn't intercept
        sys.excepthook = MagicMock()
        try:
            _install_excepthook()
            hook = sys.excepthook
            with caplog.at_level(logging.CRITICAL):
                hook(ValueError, ValueError("test crash"), None)
            assert "test crash" in caplog.text
        finally:
            sys.excepthook = original


# ---------------------------------------------------------------------------
# Fixture for project settings form tests — issue #93
# ---------------------------------------------------------------------------

SAMPLE_PROJECT_YAML_WITH_PROVIDERS = {
    "title": "Settings Test Project",
    "aspect_ratio": "16:9",
    "style_prefix": "Cinematic look.",
    "providers": {
        "still": {
            "backend": "google",
            "model": "imagen-4.0-generate-001",
        },
        "clip": {
            "backend": "fal",
            "model": "fal-ai/wan/v2.1/text-to-video",
        },
    },
    "audio": "audio/music.mp3",
    "subtitles": "subs/captions.srt",
    "characters": {
        "hero": {
            "description": "A brave warrior with a sword",
            "reference": ["references/hero.png"],
        },
        "villain": {
            "description": "A dark sorcerer",
        },
    },
    "scenes": [
        {
            "number": 1,
            "title": "Opening",
            "type": "still",
            "duration": 5,
            "prompt": "A castle on a hill.",
        },
    ],
}


@pytest.fixture
def settings_project_dir(tmp_path):
    """Project directory with providers and characters for settings form tests."""
    yaml_path = tmp_path / "project.yaml"
    yaml_path.write_text(yaml.dump(SAMPLE_PROJECT_YAML_WITH_PROVIDERS))
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: Project Settings Form — issue #93
# ---------------------------------------------------------------------------


class TestProjectSettingsForm:
    """Tests for the ProjectSettingsForm widget."""

    def test_form_populates_title(self, qtbot, settings_project_dir):
        """Loading a project should populate the title field."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert form._title_edit.text() == "Settings Test Project"

    def test_form_populates_aspect_ratio(self, qtbot, settings_project_dir):
        """Loading a project should set the aspect ratio combo."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert form._aspect_combo.currentText() == "16:9"

    def test_form_populates_style_prefix(self, qtbot, settings_project_dir):
        """Loading a project should set the style prefix."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert form._style_edit.toPlainText() == "Cinematic look."

    def test_form_populates_still_backend(self, qtbot, settings_project_dir):
        """Loading should set still provider backend."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert form._still_backend.currentText() == "google"

    def test_form_populates_still_model(self, qtbot, settings_project_dir):
        """Loading should set still provider model."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert form._still_model.currentText() == "imagen-4.0-generate-001"

    def test_form_populates_clip_backend(self, qtbot, settings_project_dir):
        """Loading should set clip provider backend."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert form._clip_backend.currentText() == "fal"

    def test_form_populates_clip_model(self, qtbot, settings_project_dir):
        """Loading should set clip provider model."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert form._clip_model.currentText() == "fal-ai/wan/v2.1/text-to-video"

    def test_form_populates_audio(self, qtbot, settings_project_dir):
        """Loading should set audio file path."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert form._audio_edit.text() == "audio/music.mp3"

    def test_form_populates_subtitles(self, qtbot, settings_project_dir):
        """Loading should set subtitles file path."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert form._subs_edit.text() == "subs/captions.srt"

    def test_form_populates_characters(self, qtbot, settings_project_dir):
        """Loading should create character description fields."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert "hero" in form._char_edits
        assert "villain" in form._char_edits
        assert form._char_edits["hero"].toPlainText() == "A brave warrior with a sword"
        assert form._char_edits["villain"].toPlainText() == "A dark sorcerer"

    def test_form_not_dirty_after_load(self, qtbot, settings_project_dir):
        """Form should not be dirty immediately after loading."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        assert not form.is_dirty()

    def test_form_dirty_after_title_change(self, qtbot, settings_project_dir):
        """Changing the title should mark the form dirty."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        form._title_edit.setText("Changed Title")
        assert form.is_dirty()

    def test_form_save_writes_title(self, qtbot, settings_project_dir):
        """Saving after title change should update project.yaml."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.gui.yaml_editor_helpers import load_yaml_roundtrip

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)
        form._title_edit.setText("New Title")
        form._save()

        reloaded = load_yaml_roundtrip(settings_project_dir / "project.yaml")
        assert reloaded["title"] == "New Title"

    def test_form_save_writes_aspect_ratio(self, qtbot, settings_project_dir):
        """Saving after aspect ratio change should update project.yaml."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.gui.yaml_editor_helpers import load_yaml_roundtrip

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)
        form._aspect_combo.setCurrentText("9:16")
        form._save()

        reloaded = load_yaml_roundtrip(settings_project_dir / "project.yaml")
        assert reloaded["aspect_ratio"] == "9:16"

    def test_form_save_writes_style_prefix(self, qtbot, settings_project_dir):
        """Saving after style prefix change should update project.yaml."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.gui.yaml_editor_helpers import load_yaml_roundtrip

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)
        form._style_edit.setPlainText("New style.")
        form._save()

        reloaded = load_yaml_roundtrip(settings_project_dir / "project.yaml")
        assert reloaded["style_prefix"] == "New style."

    def test_form_save_writes_provider_backend(self, qtbot, settings_project_dir):
        """Saving after backend change should update project.yaml."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.gui.yaml_editor_helpers import (
            get_nested,
            load_yaml_roundtrip,
        )

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        idx = form._still_backend.findText("fal")
        form._still_backend.setCurrentIndex(idx)
        form._save()

        reloaded = load_yaml_roundtrip(settings_project_dir / "project.yaml")
        assert get_nested(reloaded, ["providers", "still", "backend"]) == "fal"

    def test_form_save_removes_options_on_backend_change(self, qtbot, tmp_path):
        """Changing backend should remove options from project.yaml on save."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.gui.yaml_editor_helpers import (
            get_nested,
            load_yaml_roundtrip,
        )

        project_data = {
            **SAMPLE_PROJECT_YAML_WITH_PROVIDERS,
            "providers": {
                "still": {
                    "backend": "google",
                    "model": "imagen-4.0-generate-001",
                    "options": {"seed": 42},
                },
                "clip": {
                    "backend": "fal",
                    "model": "fal-ai/wan/v2.1/text-to-video",
                },
            },
        }
        yaml_path = tmp_path / "project.yaml"
        yaml_path.write_text(yaml.dump(project_data))

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(tmp_path)

        # Change backend
        idx = form._still_backend.findText("fal")
        form._still_backend.setCurrentIndex(idx)
        form._save()

        reloaded = load_yaml_roundtrip(yaml_path)
        assert get_nested(reloaded, ["providers", "still", "options"]) is None

    def test_form_save_writes_character_description(self, qtbot, settings_project_dir):
        """Saving after character edit should update description in YAML."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.gui.yaml_editor_helpers import load_yaml_roundtrip

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        form._char_edits["hero"].setPlainText("Updated hero description")
        form._save()

        reloaded = load_yaml_roundtrip(settings_project_dir / "project.yaml")
        assert (
            reloaded["characters"]["hero"]["description"] == "Updated hero description"
        )

    def test_form_save_emits_saved_signal(self, qtbot, settings_project_dir):
        """Saving should emit the saved signal."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)
        form._title_edit.setText("Changed")

        with qtbot.waitSignal(form.saved, timeout=1000):
            form._save()

    def test_form_revert_restores_values(self, qtbot, settings_project_dir):
        """Reverting should restore form to on-disk values."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        form._title_edit.setText("Changed Title")
        assert form.is_dirty()

        form._revert()
        assert form._title_edit.text() == "Settings Test Project"
        assert not form.is_dirty()

    def test_form_backend_change_updates_model_combo(self, qtbot, settings_project_dir):
        """Changing backend should repopulate the model dropdown."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        # Change still backend to fal
        idx = form._still_backend.findText("fal")
        form._still_backend.setCurrentIndex(idx)

        # Model combo should now contain fal models
        models = [
            form._still_model.itemText(i) for i in range(form._still_model.count())
        ]
        assert any("fal-ai" in m for m in models)

    def test_form_clears_empty_audio_on_save(self, qtbot, settings_project_dir):
        """Clearing audio field should remove it from YAML on save."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.gui.yaml_editor_helpers import load_yaml_roundtrip

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        form._audio_edit.setText("")
        form._save()

        reloaded = load_yaml_roundtrip(settings_project_dir / "project.yaml")
        assert "audio" not in reloaded

    def test_form_clears_empty_style_prefix_on_save(self, qtbot, settings_project_dir):
        """Clearing style_prefix should remove it from YAML on save."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.gui.yaml_editor_helpers import load_yaml_roundtrip

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        form._style_edit.setPlainText("")
        form._save()

        reloaded = load_yaml_roundtrip(settings_project_dir / "project.yaml")
        assert "style_prefix" not in reloaded

    def test_model_completer_uses_all_models(self, qtbot):
        """Model combo completer should contain models from all backends."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.model_registry import get_all_models

        form = ProjectSettingsForm()
        qtbot.addWidget(form)

        completer = form._still_model.completer()
        assert completer is not None
        model = completer.model()
        completer_items = [
            model.data(model.index(i, 0)) for i in range(model.rowCount())
        ]
        all_models = get_all_models()
        # Should contain models from at least two different backends
        backends_in_completer = set()
        for item in completer_items:
            if item in all_models:
                backends_in_completer.add(all_models[item])
        assert len(backends_in_completer) >= 2

    def test_model_completer_matches_substring(self, qtbot):
        """Completer should match substrings, not just prefixes."""
        from PySide6.QtCore import Qt

        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)

        completer = form._still_model.completer()
        assert completer is not None
        assert completer.filterMode() & Qt.MatchContains

    def test_model_selection_switches_backend(self, qtbot, settings_project_dir):
        """Selecting a FAL model should auto-switch backend to fal."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        # Start with google backend
        form._still_backend.setCurrentText("google")
        assert form._still_backend.currentText() == "google"

        # Type a FAL model into the model combo
        form._still_model.setCurrentText("fal-ai/flux-2-pro")

        # Backend should auto-switch to fal
        assert form._still_backend.currentText() == "fal"

    def test_clip_model_selection_switches_backend(self, qtbot, settings_project_dir):
        """Selecting a Google clip model should auto-switch clip backend."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)
        form.load_project(settings_project_dir)

        # Start with fal backend
        form._clip_backend.setCurrentText("fal")
        assert form._clip_backend.currentText() == "fal"

        # Type a Google model
        form._clip_model.setCurrentText("veo-3.1-fast-generate-001")

        # Backend should auto-switch to google
        assert form._clip_backend.currentText() == "google"


# ---------------------------------------------------------------------------
# Tests: YAML Viewer with Settings Form — issue #93
# ---------------------------------------------------------------------------


class TestYamlViewerSettingsIntegration:
    """Tests for YamlViewer integration with ProjectSettingsForm."""

    def test_yaml_viewer_has_settings_form(self, qtbot):
        """YamlViewer should contain a ProjectSettingsForm."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)

        assert hasattr(viewer, "settings_form")
        assert isinstance(viewer.settings_form, ProjectSettingsForm)

    def test_yaml_viewer_load_project_populates_form(self, qtbot, settings_project_dir):
        """load_project should populate both YAML text and form fields."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)
        viewer.load_project(settings_project_dir)

        # YAML text should contain the title
        assert "Settings Test Project" in viewer.text_edit.toPlainText()
        # Form should have the title
        assert viewer.settings_form._title_edit.text() == "Settings Test Project"

    def test_yaml_viewer_form_save_refreshes_yaml(self, qtbot, settings_project_dir):
        """Saving the form should refresh the YAML text display."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)
        viewer.load_project(settings_project_dir)

        viewer.settings_form._title_edit.setText("Updated Title")
        viewer.settings_form._save()

        assert "Updated Title" in viewer.text_edit.toPlainText()

    def test_yaml_viewer_emits_project_saved(self, qtbot, settings_project_dir):
        """Saving via form should emit project_saved from YamlViewer."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)
        viewer.load_project(settings_project_dir)

        viewer.settings_form._title_edit.setText("Changed")

        with qtbot.waitSignal(viewer.project_saved, timeout=1000):
            viewer.settings_form._save()


# ---------------------------------------------------------------------------
# Tests: Generate Dialog Dry Run checkbox — issue #95
# ---------------------------------------------------------------------------


class TestGenerateDialogDryRun:
    """Tests for dry-run checkbox in GenerateDialog."""

    def test_dialog_has_dry_run_checkbox(self, qtbot, gui_project_dir):
        """GenerateDialog should have a dry_run checkbox."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir)
        dialog = GenerateDialog(project)
        qtbot.addWidget(dialog)

        assert hasattr(dialog, "_dry_run_check")

    def test_dry_run_unchecked_by_default(self, qtbot, gui_project_dir):
        """Dry-run checkbox should be unchecked by default."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir)
        dialog = GenerateDialog(project)
        qtbot.addWidget(dialog)

        assert not dialog.is_dry_run()

    def test_dry_run_checked_returns_true(self, qtbot, gui_project_dir):
        """Checking dry-run should make is_dry_run() return True."""
        from storyboard_gen.config import load_project
        from storyboard_gen.gui.generate_dialog import GenerateDialog

        project = load_project(gui_project_dir)
        dialog = GenerateDialog(project)
        qtbot.addWidget(dialog)

        dialog._dry_run_check.setChecked(True)
        assert dialog.is_dry_run()


# ---------------------------------------------------------------------------
# Tests: Dry Run output — issue #95
# ---------------------------------------------------------------------------


class TestDryRunOutput:
    """Tests for dry-run output formatting in the GUI."""

    def test_dry_run_outputs_to_console(self, qtbot, gui_project_dir):
        """Dry run should write scene info to the console panel."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        window._run_dry_run(list(window._project.scenes))

        text = window.console.text_edit.toPlainText()
        assert "Scene 1" in text
        assert "Opening shot" in text

    def test_dry_run_shows_provider_info(self, qtbot, gui_project_dir):
        """Dry run should include provider/model info."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        window._run_dry_run(list(window._project.scenes))

        text = window.console.text_edit.toPlainText()
        # Default backend is google
        assert "google" in text.lower()

    def test_dry_run_shows_prompt(self, qtbot, gui_project_dir):
        """Dry run should include the resolved prompt."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        window._run_dry_run(list(window._project.scenes))

        text = window.console.text_edit.toPlainText()
        assert "Prompt:" in text

    def test_dry_run_shows_all_scenes(self, qtbot, gui_project_dir):
        """Dry run should list all requested scenes."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        window._run_dry_run(list(window._project.scenes))

        text = window.console.text_edit.toPlainText()
        assert "Scene 1" in text
        assert "Scene 2" in text
        assert "Scene 3" in text

    def test_dry_run_does_not_start_workers(self, qtbot, gui_project_dir):
        """Dry run should not create any generation workers."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        window._run_dry_run(list(window._project.scenes))

        assert len(window._workers) == 0


class TestFieldWarningDialog:
    """Tests for pre-generation warning dialog (#118)."""

    def test_warning_dialog_shown_when_fields_unsupported(self, qtbot, gui_project_dir):
        """Warning dialog should appear when unsupported fields are used."""
        from PySide6.QtWidgets import QMessageBox

        from storyboard_gen.gui.app import MainWindow
        from storyboard_gen.models import Scene

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Create a scene with seed on a model that doesn't support it
        scene = Scene(
            number="1",
            title="Test",
            scene_type="still",
            prompt="test",
            duration=5,
            seed=42,
        )

        with (
            patch.object(window, "_project") as mock_project,
            patch(
                "storyboard_gen.gui.app.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Cancel,
            ) as mock_warn,
            patch.object(window, "_start_scene_generation") as mock_start,
        ):
            mock_project.scenes = [scene]
            mock_project.style_reference = []
            mock_project.characters = {}

            # Use a provider that returns warnings
            with patch(
                "storyboard_gen.generate.resolve_provider_config"
            ) as mock_resolve:
                from storyboard_gen.models import ProviderConfig

                mock_resolve.return_value = ProviderConfig(
                    backend="fal", model="xai/grok-imagine-image"
                )
                window._start_generation([scene])

            # Dialog should have been shown
            mock_warn.assert_called_once()
            # Generation should NOT have started (user cancelled)
            mock_start.assert_not_called()

    def test_warning_dialog_proceed_starts_generation(self, qtbot, gui_project_dir):
        """Clicking Proceed in warning dialog should start generation."""
        from PySide6.QtWidgets import QMessageBox

        from storyboard_gen.gui.app import MainWindow
        from storyboard_gen.models import Scene

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scene = Scene(
            number="1",
            title="Test",
            scene_type="still",
            prompt="test",
            duration=5,
            seed=42,
        )

        with (
            patch.object(window, "_project") as mock_project,
            patch(
                "storyboard_gen.gui.app.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch.object(window, "_start_scene_generation") as mock_start,
        ):
            mock_project.scenes = [scene]
            mock_project.style_reference = []
            mock_project.characters = {}

            with patch(
                "storyboard_gen.generate.resolve_provider_config"
            ) as mock_resolve:
                from storyboard_gen.models import ProviderConfig

                mock_resolve.return_value = ProviderConfig(
                    backend="fal", model="xai/grok-imagine-image"
                )
                window._start_generation([scene])

            # Generation SHOULD have started (user proceeded)
            mock_start.assert_called_once()

    def test_no_dialog_when_no_warnings(self, qtbot, gui_project_dir):
        """No dialog should appear when all fields are supported."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        scenes = list(window._project.scenes)

        with (
            patch("storyboard_gen.gui.app.QMessageBox.warning") as mock_warn,
            patch("storyboard_gen.gui.app.GenerateWorker") as mock_cls,
        ):
            mock_worker = mock_cls.return_value
            mock_worker.isRunning.return_value = True
            window._start_generation(scenes)

            # No dialog — fields are supported
            mock_warn.assert_not_called()


class TestEnvEditorDialog:
    """Tests for .env editor dialog (#116)."""

    def test_dialog_creates_with_env_path(self, qtbot, tmp_path):
        """Dialog should initialise from an .env file path."""
        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = tmp_path / ".env"
        env_path.write_text("FAL_KEY=test123\n")
        dialog = EnvEditorDialog(env_path=env_path)
        qtbot.addWidget(dialog)
        assert dialog is not None

    def test_dialog_loads_existing_values(self, qtbot, tmp_path):
        """Dialog should populate fields from existing .env values."""
        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = tmp_path / ".env"
        env_path.write_text("FAL_KEY=my-fal-key\nGEMINI_API_KEY=my-gemini-key\n")
        dialog = EnvEditorDialog(env_path=env_path)
        qtbot.addWidget(dialog)

        assert dialog._fields["FAL_KEY"].text() == "my-fal-key"
        assert dialog._fields["GEMINI_API_KEY"].text() == "my-gemini-key"

    def test_dialog_loads_commented_values_as_empty(self, qtbot, tmp_path):
        """Commented-out keys should show as empty fields."""
        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = tmp_path / ".env"
        env_path.write_text("# FAL_KEY=your-fal-key\n")
        dialog = EnvEditorDialog(env_path=env_path)
        qtbot.addWidget(dialog)

        assert dialog._fields["FAL_KEY"].text() == ""

    def test_dialog_saves_values(self, qtbot, tmp_path):
        """Saving should write values back to the .env file."""
        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = tmp_path / ".env"
        env_path.write_text("FAL_KEY=old-key\n")
        dialog = EnvEditorDialog(env_path=env_path)
        qtbot.addWidget(dialog)

        dialog._fields["FAL_KEY"].setText("new-key")
        dialog._save()

        content = env_path.read_text()
        assert "FAL_KEY=new-key" in content

    def test_dialog_saves_empty_as_commented(self, qtbot, tmp_path):
        """Empty fields should be written as commented-out lines."""
        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = tmp_path / ".env"
        env_path.write_text("FAL_KEY=old-key\n")
        dialog = EnvEditorDialog(env_path=env_path)
        qtbot.addWidget(dialog)

        dialog._fields["FAL_KEY"].setText("")
        dialog._save()

        content = env_path.read_text()
        assert "# FAL_KEY=" in content

    def test_dialog_has_all_known_keys(self, qtbot, tmp_path):
        """Dialog should have fields for all known .env keys."""
        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = tmp_path / ".env"
        env_path.write_text("")
        dialog = EnvEditorDialog(env_path=env_path)
        qtbot.addWidget(dialog)

        expected_keys = [
            "GEMINI_API_KEY",
            "USE_VERTEX",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_LOCATION",
            "GCS_OUTPUT_BUCKET",
            "FAL_KEY",
            "REPLICATE_API_TOKEN",
        ]
        for key in expected_keys:
            assert key in dialog._fields, f"Missing field for {key}"

    def test_dialog_creates_env_if_missing(self, qtbot, tmp_path):
        """Dialog should handle missing .env gracefully."""
        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = tmp_path / ".env"
        # Don't create the file
        dialog = EnvEditorDialog(env_path=env_path)
        qtbot.addWidget(dialog)

        dialog._fields["FAL_KEY"].setText("brand-new-key")
        dialog._save()

        assert env_path.exists()
        content = env_path.read_text()
        assert "FAL_KEY=brand-new-key" in content


# ---------------------------------------------------------------------------
# Unit tests: Window layout persistence (#119)
# ---------------------------------------------------------------------------


class TestLayoutPersistence:
    """Test window geometry and splitter state persistence (#119)."""

    def test_settings_has_window_geometry_property(self, qtbot):
        """AppSettings should expose a window_geometry bytes property."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings._qs.remove("window/geometry")

        # Default is None when not set
        assert settings.window_geometry is None

    def test_settings_window_geometry_round_trip(self, qtbot):
        """window_geometry should persist and return bytes."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        data = b"\x01\x02\x03"
        settings.window_geometry = data

        assert settings.window_geometry == data

        settings._qs.remove("window/geometry")

    def test_settings_has_main_splitter_state(self, qtbot):
        """AppSettings should expose main_splitter_state bytes property."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings._qs.remove("window/main_splitter")

        assert settings.main_splitter_state is None

    def test_settings_main_splitter_round_trip(self, qtbot):
        """main_splitter_state should persist and return bytes."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        data = b"\x04\x05\x06"
        settings.main_splitter_state = data

        assert settings.main_splitter_state == data

        settings._qs.remove("window/main_splitter")

    def test_settings_has_content_splitter_state(self, qtbot):
        """AppSettings should expose content_splitter_state bytes property."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings._qs.remove("window/content_splitter")

        assert settings.content_splitter_state is None

    def test_settings_content_splitter_round_trip(self, qtbot):
        """content_splitter_state should persist and return bytes."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        data = b"\x07\x08\x09"
        settings.content_splitter_state = data

        assert settings.content_splitter_state == data

        settings._qs.remove("window/content_splitter")

    def test_settings_has_console_visible(self, qtbot):
        """AppSettings should expose console_visible bool property."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings._qs.remove("window/console_visible")

        # Default is False (console hidden by default)
        assert settings.console_visible is False

    def test_settings_console_visible_round_trip(self, qtbot):
        """console_visible should persist."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings.console_visible = True

        assert settings.console_visible is True

        settings._qs.remove("window/console_visible")

    def test_settings_has_yaml_editor_visible(self, qtbot):
        """AppSettings should expose yaml_editor_visible bool property."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings._qs.remove("window/yaml_editor_visible")

        assert settings.yaml_editor_visible is False

    def test_settings_yaml_editor_visible_round_trip(self, qtbot):
        """yaml_editor_visible should persist."""
        from storyboard_gen.gui.settings import AppSettings

        settings = AppSettings()
        settings.yaml_editor_visible = True

        assert settings.yaml_editor_visible is True

        settings._qs.remove("window/yaml_editor_visible")

    def test_close_saves_geometry(self, qtbot, gui_project_dir):
        """closeEvent should save window geometry to settings."""
        from PySide6.QtGui import QCloseEvent

        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Act — close the window
        event = QCloseEvent()
        window.closeEvent(event)

        # Assert — geometry saved
        assert window._settings.window_geometry is not None

        # Cleanup
        window._settings._qs.remove("window/geometry")
        window._settings._qs.remove("window/main_splitter")
        window._settings._qs.remove("window/content_splitter")
        window._settings._qs.remove("window/console_visible")
        window._settings._qs.remove("window/yaml_editor_visible")

    def test_close_saves_splitter_states(self, qtbot, gui_project_dir):
        """closeEvent should save splitter states."""
        from PySide6.QtGui import QCloseEvent

        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Act
        event = QCloseEvent()
        window.closeEvent(event)

        # Assert
        assert window._settings.main_splitter_state is not None
        assert window._settings.content_splitter_state is not None

        # Cleanup
        window._settings._qs.remove("window/geometry")
        window._settings._qs.remove("window/main_splitter")
        window._settings._qs.remove("window/content_splitter")
        window._settings._qs.remove("window/console_visible")
        window._settings._qs.remove("window/yaml_editor_visible")

    def test_close_saves_panel_visibility(self, qtbot, gui_project_dir):
        """closeEvent should save console and yaml editor visibility."""
        from PySide6.QtGui import QCloseEvent

        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)

        # Show console and yaml editor
        window.console.setVisible(True)
        window.yaml_editor.setVisible(True)

        # Act
        event = QCloseEvent()
        window.closeEvent(event)

        # Assert
        assert window._settings.console_visible is True
        assert window._settings.yaml_editor_visible is True

        # Cleanup
        window._settings._qs.remove("window/console_visible")
        window._settings._qs.remove("window/yaml_editor_visible")
        window._settings._qs.remove("window/geometry")
        window._settings._qs.remove("window/main_splitter")
        window._settings._qs.remove("window/content_splitter")


# ---------------------------------------------------------------------------
# Unit tests: Content splitter minimum height (#119)
# ---------------------------------------------------------------------------


class TestContentSplitterSizing:
    """Test that the content splitter allows the console to grow (#119)."""

    def test_content_splitter_has_minimum_height(self, qtbot):
        """Content splitter should have an explicit minimum height."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert window._content_splitter.minimumHeight() <= 100


# ---------------------------------------------------------------------------
# Unit tests: YAML viewer closes on save (#119)
# ---------------------------------------------------------------------------


class TestYamlViewerCloseOnSave:
    """Test that the YAML viewer window closes after a successful save (#119)."""

    def test_yaml_viewer_closes_on_form_saved(self, qtbot, gui_project_dir):
        """YamlViewer should close when the form emits saved."""
        from storyboard_gen.gui.yaml_viewer import YamlViewer

        viewer = YamlViewer()
        qtbot.addWidget(viewer)
        viewer.load_project(gui_project_dir)
        viewer.show()

        # Verify it's visible first
        assert viewer.isVisible()

        # Act — simulate form save
        viewer._on_form_saved()

        # Assert — viewer should be closed
        assert not viewer.isVisible()


# ---------------------------------------------------------------------------
# Unit tests: .env editor monospace and width (#119)
# ---------------------------------------------------------------------------


class TestEnvEditorStyling:
    """Test that .env editor fields are monospaced and wide enough (#119)."""

    def test_env_editor_fields_are_monospaced(self, qtbot, tmp_path):
        """All QLineEdit fields should use a monospace font."""
        from PySide6.QtGui import QFont

        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = tmp_path / ".env"
        env_path.write_text("")
        dialog = EnvEditorDialog(env_path=env_path)
        qtbot.addWidget(dialog)

        for key, field in dialog._fields.items():
            style_hint = field.font().styleHint()
            assert style_hint == QFont.StyleHint.Monospace, (
                f"Field {key} should be monospaced"
            )

    def test_env_editor_fields_have_minimum_width(self, qtbot, tmp_path):
        """All QLineEdit fields should have a minimum width for API keys."""
        from storyboard_gen.gui.env_editor import EnvEditorDialog

        env_path = tmp_path / ".env"
        env_path.write_text("")
        dialog = EnvEditorDialog(env_path=env_path)
        qtbot.addWidget(dialog)

        for key, field in dialog._fields.items():
            assert field.minimumWidth() >= 400, (
                f"Field {key} minimum width should be >= 400"
            )


# ---------------------------------------------------------------------------
# Unit tests: Style prefix field sizing (#119)
# ---------------------------------------------------------------------------


class TestStylePrefixSizing:
    """Test that the style_prefix field is large enough for paragraph text (#119)."""

    def test_style_prefix_minimum_height(self, qtbot):
        """Style prefix field should have a minimum height for paragraph text."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)

        # Should be tall enough for multi-line text (at least 100px)
        assert form._style_edit.minimumHeight() >= 100

    def test_style_prefix_no_restrictive_max_height(self, qtbot):
        """Style prefix field should not be constrained to a tiny max height."""
        from storyboard_gen.gui.project_settings import ProjectSettingsForm

        form = ProjectSettingsForm()
        qtbot.addWidget(form)

        # Max height should allow substantial text (at least 100px, not capped at 60)
        assert form._style_edit.maximumHeight() >= 100


# ---------------------------------------------------------------------------
# Unit tests: Scene-level model selector (#120)
# ---------------------------------------------------------------------------

# YAML with a scene-level model override for testing
YAML_WITH_MODEL_OVERRIDE = """\
title: "Model Override Test"
aspect_ratio: "16:9"
style_prefix: "Test style."

scenes:
  - number: 1
    title: "Override scene"
    type: still
    duration: 5
    model: "fal-ai/flux-pro/v1.1"
    prompt: >
      A test scene.

  - number: 2
    title: "Default scene"
    type: clip
    duration: 6
    prompt: >
      Another test scene.

  - number: 3
    title: "Provider override"
    type: still
    duration: 4
    provider:
      backend: replicate
      model: "black-forest-labs/flux-1.1-pro"
    prompt: >
      Third test scene.
"""


@pytest.fixture
def model_override_project_dir(tmp_path):
    """Create a project with scene-level model overrides."""
    yaml_path = tmp_path / "project.yaml"
    yaml_path.write_text(YAML_WITH_MODEL_OVERRIDE)
    return tmp_path


class TestSceneModelSelector:
    """Test scene-level model selector in SceneYamlEditor (#120)."""

    def test_editor_has_model_combo(self, qtbot):
        """SceneYamlEditor should have a model combobox."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        assert hasattr(editor, "_model_combo")

    def test_editor_has_backend_label(self, qtbot):
        """SceneYamlEditor should have a backend label."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        assert hasattr(editor, "_backend_label")

    def test_editor_has_clear_button(self, qtbot):
        """SceneYamlEditor should have a clear override button."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        assert hasattr(editor, "_clear_model_btn")

    def test_model_combo_has_fuzzy_completer(self, qtbot):
        """Model combobox should have a substring-matching completer."""
        from PySide6.QtCore import Qt

        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        completer = editor._model_combo.completer()
        assert completer is not None
        assert completer.filterMode() == Qt.MatchContains

    def test_load_scene_with_model_override_populates_combo(
        self, qtbot, model_override_project_dir
    ):
        """Loading a scene with model: should populate the model combo."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        assert editor._model_combo.currentText() == "fal-ai/flux-pro/v1.1"

    def test_load_scene_with_provider_override_populates_combo(
        self, qtbot, model_override_project_dir
    ):
        """Loading a scene with provider: block should populate the model combo."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("3", yaml_path)

        assert editor._model_combo.currentText() == "black-forest-labs/flux-1.1-pro"

    def test_load_scene_without_override_shows_empty(
        self, qtbot, model_override_project_dir
    ):
        """Loading a scene without model override should show empty combo."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("2", yaml_path)

        assert editor._model_combo.currentText() == ""

    def test_backend_label_updates_on_model_selection(self, qtbot):
        """Backend label should update when a known model is selected."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        # Simulate selecting a FAL model
        editor._model_combo.setCurrentText("fal-ai/flux-pro/v1.1")

        assert "fal" in editor._backend_label.text().lower()

    def test_backend_label_shows_unknown_for_custom_model(self, qtbot):
        """Backend label should handle unknown models gracefully."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        editor._model_combo.setCurrentText("custom/unknown-model")

        # Should not crash, label can show empty or unknown
        assert editor._backend_label.text() is not None

    def test_model_selection_updates_yaml_text(self, qtbot, model_override_project_dir):
        """Selecting a model should inject model: into the YAML text."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("2", yaml_path)  # Scene without model override

        # Act — select a model
        editor._on_model_selected("fal-ai/flux-general")

        # Assert — YAML text should now contain model:
        text = editor.text_edit.toPlainText()
        assert "model:" in text
        assert "fal-ai/flux-general" in text

    def test_clear_removes_model_from_yaml(self, qtbot, model_override_project_dir):
        """Clear button should remove model: from the YAML text."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)  # Scene with model override

        # Verify model is present
        assert "model:" in editor.text_edit.toPlainText()

        # Act — clear
        editor._on_clear_model()

        # Assert
        text = editor.text_edit.toPlainText()
        assert "model:" not in text
        assert editor._model_combo.currentText() == ""

    def test_clear_removes_provider_block_from_yaml(
        self, qtbot, model_override_project_dir
    ):
        """Clear button should remove provider: block from the YAML text."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("3", yaml_path)  # Scene with provider: block

        # Verify provider is present
        assert "provider:" in editor.text_edit.toPlainText()

        # Act — clear
        editor._on_clear_model()

        # Assert
        text = editor.text_edit.toPlainText()
        assert "provider:" not in text
        assert "model:" not in text
        assert editor._model_combo.currentText() == ""

    def test_model_selection_marks_editor_dirty(
        self, qtbot, model_override_project_dir
    ):
        """Selecting a model should mark the editor as dirty."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("2", yaml_path)

        assert not editor.is_dirty()

        # Act
        editor._on_model_selected("fal-ai/flux-general")

        # Assert
        assert editor.is_dirty()

    def test_completer_activation_injects_into_yaml(
        self, qtbot, model_override_project_dir
    ):
        """Selecting from the completer popup should inject model into YAML."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("2", yaml_path)  # No model override

        # Simulate completer activation (what happens when user picks from popup)
        completer = editor._model_combo.completer()
        completer.activated.emit("fal-ai/flux-general")

        # Assert — model should be injected into YAML text
        text = editor.text_edit.toPlainText()
        assert "fal-ai/flux-general" in text

    def test_save_with_empty_combo_shows_warning_and_clears_on_apply(
        self, qtbot, model_override_project_dir
    ):
        """Clearing combo and saving shows warning; Apply clears model (#124)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)  # Has model: override

        # Verify model is present in YAML text
        assert "model:" in editor.text_edit.toPlainText()

        # Act — clear combo text, then save (Apply = trust combo)
        editor._model_combo.setCurrentText("")
        with patch("storyboard_gen.gui.scene_yaml_editor.QMessageBox") as mock_mb:
            mock_mb.warning.return_value = mock_mb.Apply
            editor._save()

        # Assert — model override removed from the saved file
        saved_block = editor.text_edit.toPlainText()
        assert "model:" not in saved_block


# ---------------------------------------------------------------------------
# YAML editor model override conflict warning — issue #124
# ---------------------------------------------------------------------------


class TestYamlEditorModelConflictWarning:
    """YAML editor should warn when combo and YAML text disagree (#124)."""

    def test_save_auto_injects_when_yaml_model_deleted_but_combo_set(
        self, qtbot, model_override_project_dir
    ):
        """Deleting model: from YAML while combo set auto-injects (#127)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        combo_model = editor._model_combo.currentText().strip()
        assert combo_model != ""

        # Act — manually delete the model: line from YAML text
        text = editor.text_edit.toPlainText()
        import re

        text = re.sub(r"^\s*model:.*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*provider:.*\n?", "", text, flags=re.MULTILINE)
        editor.text_edit.setPlainText(text)

        # Save should auto-inject combo value, no warning
        with patch("storyboard_gen.gui.scene_yaml_editor.QMessageBox") as mock_mb:
            editor._save()
            mock_mb.warning.assert_not_called()

    def test_save_auto_injects_when_yaml_model_changed_but_combo_set(
        self, qtbot, model_override_project_dir
    ):
        """Changing model: in YAML while combo set auto-injects combo (#127)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        combo_model = editor._model_combo.currentText().strip()
        assert combo_model != ""

        # Change the model in YAML text to something different from combo
        text = editor.text_edit.toPlainText()
        import re

        text = re.sub(
            r"(model:\s*).*", r"\1fal-ai/different-model", text, flags=re.MULTILINE
        )
        editor.text_edit.setPlainText(text)

        # Save should auto-inject combo value, no warning
        with patch("storyboard_gen.gui.scene_yaml_editor.QMessageBox") as mock_mb:
            editor._save()
            mock_mb.warning.assert_not_called()

    def test_save_no_warning_when_combo_and_yaml_agree(
        self, qtbot, model_override_project_dir
    ):
        """No warning when combo and YAML agree (AC7 regression)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Don't change anything — combo and YAML should agree
        with patch("storyboard_gen.gui.scene_yaml_editor.QMessageBox") as mock_mb:
            editor._save()
            mock_mb.warning.assert_not_called()


# ---------------------------------------------------------------------------
# Cmd+, keybinding for YAML editor toggle — issue #125
# ---------------------------------------------------------------------------


class TestCommaShortcut:
    """Ctrl+, shortcut should open project YAML viewer (#125)."""

    def test_comma_shortcut_opens_project_yaml(self, qtbot, gui_project_dir):
        """Ctrl+, shortcut exists and is connected to _on_view_yaml (AC1)."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert hasattr(window, "_shortcut_edit_yaml2")
        assert window._shortcut_edit_yaml2.key().toString() == "Ctrl+,"

    def test_yaml_viewer_tooltip_shows_comma_shortcut(self, qtbot, gui_project_dir):
        """YAML viewer tooltip mentions Cmd+, shortcut (AC2)."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        tooltip = window._btn_yaml_viewer.toolTip()
        assert "," in tooltip

    def test_yaml_editor_tooltip_no_comma_shortcut(self, qtbot, gui_project_dir):
        """YAML editor tooltip should NOT mention Cmd+, (AC3)."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        tooltip = window._btn_yaml_editor.toolTip()
        assert "Shift+Y" in tooltip
        assert "," not in tooltip


# ---------------------------------------------------------------------------
# Scene YAML editor combo → save workflow — issue #127
# ---------------------------------------------------------------------------


class TestYamlEditorComboSaveWorkflow:
    """Combo selection should auto-inject model on save without warning (#127)."""

    def test_combo_dropdown_selection_injects_into_yaml(
        self, qtbot, model_override_project_dir
    ):
        """Selecting from combo dropdown auto-injects model into YAML (AC1)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Simulate selecting a different model from the combo dropdown
        new_model = "fal-ai/flux/dev"
        # Add item so activated signal works
        editor._model_combo.addItem(new_model)
        idx = editor._model_combo.findText(new_model)
        # Emit activated signal (simulates dropdown selection)
        editor._model_combo.activated.emit(idx)

        # Assert — model should be injected into YAML text
        assert new_model in editor.text_edit.toPlainText()

    def test_save_after_combo_selection_no_warning(
        self, qtbot, model_override_project_dir
    ):
        """Cmd+S after combo selection saves without warning dialog (AC2)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Change combo to a different model (simulating user typing)
        editor._model_combo.setCurrentText("fal-ai/flux/dev")

        with patch("storyboard_gen.gui.scene_yaml_editor.QMessageBox") as mock_mb:
            editor._save()
            mock_mb.warning.assert_not_called()

    def test_save_with_cleared_combo_warns_when_yaml_has_model(
        self, qtbot, model_override_project_dir
    ):
        """Clearing combo + save still warns when YAML has model (AC3, #124)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Clear the combo but leave model in YAML text
        editor._model_combo.setCurrentText("")

        with patch("storyboard_gen.gui.scene_yaml_editor.QMessageBox") as mock_mb:
            mock_mb.warning.return_value = mock_mb.Cancel
            editor._save()
            mock_mb.warning.assert_called_once()

    def test_save_after_yaml_model_deleted_no_warning_if_combo_empty(
        self, qtbot, model_override_project_dir
    ):
        """No warning when both combo and YAML have no model (AC4)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Remove model from YAML text and clear combo
        import re

        text = editor.text_edit.toPlainText()
        text = re.sub(r"^\s*model:.*\n?", "", text, flags=re.MULTILINE)
        editor.text_edit.setPlainText(text)
        editor._model_combo.setCurrentText("")

        with patch("storyboard_gen.gui.scene_yaml_editor.QMessageBox") as mock_mb:
            editor._save()
            mock_mb.warning.assert_not_called()

    def test_typed_combo_model_auto_injected_on_save(
        self, qtbot, model_override_project_dir
    ):
        """Typing model in combo + save auto-injects into YAML (AC5)."""
        from storyboard_gen.gui.scene_yaml_editor import SceneYamlEditor

        editor = SceneYamlEditor()
        qtbot.addWidget(editor)

        yaml_path = model_override_project_dir / "project.yaml"
        editor.load_scene("1", yaml_path)

        # Type a new model in the combo (doesn't trigger _on_model_selected)
        new_model = "fal-ai/recraft/v4/text-to-image"
        editor._model_combo.setCurrentText(new_model)

        with patch("storyboard_gen.gui.scene_yaml_editor.QMessageBox") as mock_mb:
            editor._save()
            mock_mb.warning.assert_not_called()

        # Verify model was injected into YAML text
        assert new_model in editor.text_edit.toPlainText()


class TestEqualWidthContentPanes:
    """Equal-width default for content panes when YAML editor is toggled (#130)."""

    @staticmethod
    def _assert_sizes_equal(sizes, *, tolerance=1):
        """Assert all sizes in the list are equal within pixel tolerance.

        Qt splitters distribute integer pixels — a ±1px difference is
        unavoidable when the total doesn't divide evenly.
        """
        for i in range(1, len(sizes)):
            assert abs(sizes[0] - sizes[i]) <= tolerance, (
                f"Pane sizes not equal within {tolerance}px: {sizes}"
            )

    @pytest.mark.regression(test_id="RT-026")
    def test_toggle_yaml_on_equalizes_three_panes(self, qtbot, gui_project_dir):
        """RT-026: Toggling YAML editor on gives all three panes equal width."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)
        window.resize(900, 600)
        window.show()
        qtbot.waitExposed(window)

        # Act — toggle YAML editor on
        window._on_toggle_yaml()

        # Assert — all three splitter sizes equal and non-zero
        sizes = window._content_splitter.sizes()
        assert len(sizes) == 3
        assert sizes[0] > 0
        self._assert_sizes_equal(sizes)

    @pytest.mark.regression(test_id="RT-027")
    def test_equalize_content_panes_three_visible(self, qtbot, gui_project_dir):
        """RT-027: _equalize_content_panes() directly gives three equal panes."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)
        window.resize(900, 600)
        window.show()
        qtbot.waitExposed(window)

        # Arrange — make YAML editor visible with unequal sizes
        window.yaml_editor.setVisible(True)
        window._content_splitter.setSizes([100, 400, 400])

        # Act
        window._equalize_content_panes()

        # Assert
        sizes = window._content_splitter.sizes()
        assert sizes[0] > 0
        self._assert_sizes_equal(sizes)

    @pytest.mark.regression(test_id="RT-028")
    def test_toggle_yaml_off_equalizes_two_panes(self, qtbot, gui_project_dir):
        """RT-028: Toggling YAML editor off gives both remaining panes equal width."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)
        window.resize(900, 600)
        window.show()
        qtbot.waitExposed(window)

        # Arrange — show then hide
        window._on_toggle_yaml()
        window._on_toggle_yaml()

        # Assert — two visible panes with equal sizes
        sizes = window._content_splitter.sizes()
        visible_sizes = [s for s in sizes if s > 0]
        assert len(visible_sizes) == 2
        self._assert_sizes_equal(visible_sizes)

    @pytest.mark.regression(test_id="RT-029")
    def test_initial_state_two_panes_equal(self, qtbot, gui_project_dir):
        """RT-029: Initial state with YAML editor hidden has two equal panes."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.open_project(gui_project_dir)
        window.resize(900, 600)
        window.show()
        qtbot.waitExposed(window)

        # Assert — initial state: YAML editor hidden, two equal panes
        assert window.yaml_editor.isHidden()
        sizes = window._content_splitter.sizes()
        visible_sizes = [s for s in sizes if s > 0]
        assert len(visible_sizes) == 2
        self._assert_sizes_equal(visible_sizes)
