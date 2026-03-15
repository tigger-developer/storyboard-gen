# ABOUTME: Background worker for single-scene generation in storyboard-gen GUI.
# ABOUTME: Runs generate_still/generate_clip in a QThread to avoid blocking the UI.

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from storyboard_gen.generate import generate_clip, generate_still
from storyboard_gen.models import Project, Scene

logger = logging.getLogger(__name__)


class GenerateWorker(QThread):
    """Background worker that generates a single scene without blocking the UI.

    Each scene gets its own worker thread. Multiple workers can run
    concurrently for different scenes.

    Emits signals for progress tracking:
    - ``scene_started(Scene)`` — when generation begins
    - ``scene_finished(Scene)`` — when generation completes
    - ``error(str)`` — if generation fails
    """

    scene_started = Signal(object)
    scene_finished = Signal(object)
    stopped = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        scene: Scene,
        project: Project,
        output_dir: Path,
        project_dir: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._scene = scene
        self.project = project
        self.output_dir = output_dir
        self.project_dir = project_dir
        self._stop_requested = False

    def request_stop(self) -> None:
        """Request the worker to stop. The current API call will complete."""
        self._stop_requested = True

    def run(self) -> None:
        """Execute generation for the single scene."""
        if self._stop_requested:
            self.stopped.emit(self._scene)
            return
        self.scene_started.emit(self._scene)
        try:
            if self._scene.scene_type == "still":
                generate_still(
                    self._scene,
                    self.project,
                    self.output_dir,
                    project_dir=self.project_dir,
                )
            else:
                generate_clip(
                    self._scene,
                    self.project,
                    self.output_dir,
                    project_dir=self.project_dir,
                )
            if self._stop_requested:
                self.stopped.emit(self._scene)
            else:
                self.scene_finished.emit(self._scene)
        except (RuntimeError, ValueError, OSError, ImportError) as exc:
            logger.error("Generation failed for scene %s: %s", self._scene.number, exc)
            self.error.emit(f"Scene {self._scene.number}: {exc}")
        except (
            Exception
        ) as exc:  # Safety net for unexpected SDK errors; specific types caught above
            logger.error(
                "Unexpected error generating scene %s: %s",
                self._scene.number,
                exc,
                exc_info=True,
            )
            self.error.emit(f"Scene {self._scene.number}: {type(exc).__name__}: {exc}")
