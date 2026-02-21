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
        """MainWindow should have toolbar actions for generation and assembly."""
        from storyboard_gen.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        # Assert — check toolbar actions
        action_texts = [a.text() for a in window.toolbar.actions() if a.text()]
        assert "Open Project" in action_texts
        assert "Generate Scene" in action_texts
        assert "All Stills" in action_texts
        assert "All Clips" in action_texts
        assert "Generate All" in action_texts
        assert "Assemble" in action_texts
        assert "Preview" in action_texts


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
