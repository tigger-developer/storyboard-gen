# ABOUTME: Background worker for scene generation in storyboard-gen GUI.
# ABOUTME: Runs generate_still/generate_clip in a QThread to avoid blocking the UI.

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from storyboard_gen.generate import generate_clip, generate_still
from storyboard_gen.models import Project, Scene

logger = logging.getLogger(__name__)


class GenerateWorker(QThread):
    """Background worker that generates scenes without blocking the UI.

    Emits signals for progress tracking:
    - ``scene_started(Scene)`` — before each scene begins
    - ``scene_finished(Scene)`` — after each scene completes
    - ``error(str)`` — if generation fails for a scene
    - ``all_finished()`` — when all scenes are done
    """

    scene_started = Signal(object)
    scene_finished = Signal(object)
    error = Signal(str)
    all_finished = Signal()

    def __init__(
        self,
        scenes: list[Scene],
        project: Project,
        output_dir: Path,
        project_dir: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.scenes = scenes
        self.project = project
        self.output_dir = output_dir
        self.project_dir = project_dir
        self._stop_requested = False

    def request_stop(self) -> None:
        """Request the worker to stop after the current scene completes."""
        self._stop_requested = True

    def run(self) -> None:
        """Execute generation for all queued scenes."""
        for scene in self.scenes:
            if self._stop_requested:
                break
            self.scene_started.emit(scene)
            try:
                if scene.scene_type == "still":
                    generate_still(
                        scene,
                        self.project,
                        self.output_dir,
                        project_dir=self.project_dir,
                    )
                else:
                    generate_clip(
                        scene,
                        self.project,
                        self.output_dir,
                        project_dir=self.project_dir,
                    )
                self.scene_finished.emit(scene)
            except (RuntimeError, ValueError, OSError) as exc:
                logger.error("Generation failed for scene %s: %s", scene.number, exc)
                self.error.emit(f"Scene {scene.number}: {exc}")
        self.all_finished.emit()
