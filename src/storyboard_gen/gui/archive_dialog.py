# ABOUTME: Archive browser dialog for reviewing and restoring previous scene outputs.
# ABOUTME: Lists archived stills/clips with timestamps and supports swapping back to current.

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyboard_gen.models import Scene, format_scene_number

# Regex to extract timestamp from archive filename: scene_NN_YYYYMMDD_HHMMSS.ext
_TIMESTAMP_RE = re.compile(r"_(\d{8}_\d{6})\.")


def get_scene_archive_dir(scene: Scene, output_dir: Path) -> Path:
    """Return the archive directory for a scene's output type.

    Args:
        scene: The scene to look up.
        output_dir: The project's output directory.

    Returns:
        Path to the archive directory (may not exist).
    """
    subdir = "stills" if scene.scene_type == "still" else "clips"
    return output_dir / subdir / "archive"


def get_scene_output_path(scene: Scene, output_dir: Path) -> Path:
    """Return the current output file path for a scene.

    Args:
        scene: The scene to look up.
        output_dir: The project's output directory.

    Returns:
        Path to the current output file (may not exist).
    """
    scene_num = format_scene_number(scene.number)
    if scene.scene_type == "still":
        return output_dir / "stills" / f"scene_{scene_num}.png"
    return output_dir / "clips" / f"scene_{scene_num}.mp4"


def parse_archive_timestamp(archive_path: Path) -> datetime | None:
    """Parse the UTC timestamp from an archive filename.

    Args:
        archive_path: Path (or just filename) of an archived file.

    Returns:
        datetime in UTC, or None if the filename doesn't match the pattern.
    """
    match = _TIMESTAMP_RE.search(archive_path.name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S").replace(
        tzinfo=timezone.utc
    )


def list_scene_archives(scene: Scene, output_dir: Path) -> list[Path]:
    """List archived versions of a scene's output, newest first.

    Args:
        scene: The scene to look up.
        output_dir: The project's output directory.

    Returns:
        List of archive file paths, sorted newest first.
    """
    archive_dir = get_scene_archive_dir(scene, output_dir)
    if not archive_dir.is_dir():
        return []

    scene_num = format_scene_number(scene.number)
    prefix = f"scene_{scene_num}_"

    archives = [p for p in archive_dir.iterdir() if p.name.startswith(prefix)]
    archives.sort(key=lambda p: p.name, reverse=True)
    return archives


def restore_archive(scene: Scene, archive_path: Path, output_dir: Path) -> None:
    """Restore an archived version as the current output.

    If a current output exists, it is moved to the archive directory
    with a new timestamp before the selected archive is restored.

    Args:
        scene: The scene being restored.
        archive_path: Path to the archived file to restore.
        output_dir: The project's output directory.
    """
    current_path = get_scene_output_path(scene, output_dir)

    # Archive the current output if it exists
    if current_path.exists():
        archive_dir = get_scene_archive_dir(scene, output_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        stem = current_path.stem
        dest = archive_dir / f"{stem}_{timestamp}{current_path.suffix}"
        current_path.rename(dest)

    # Move the selected archive to the current output path
    current_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.rename(current_path)


def _extract_thumbnail(clip_path: Path) -> QPixmap | None:
    """Extract a thumbnail frame from a video clip using ffmpeg.

    Returns None if ffmpeg is unavailable or extraction fails.
    """
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(clip_path),
                "-vframes",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "pipe:1",
            ],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout:
            pixmap = QPixmap()
            pixmap.loadFromData(result.stdout)
            if not pixmap.isNull():
                return pixmap
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


class ArchiveDialog(QDialog):
    """Dialog for browsing and restoring archived scene outputs.

    Shows a list of previously generated versions with timestamps,
    a preview area, and a Restore button to swap the selected
    archive back as the current output.
    """

    def __init__(
        self,
        scene: Scene,
        output_dir: Path,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._scene = scene
        self._output_dir = output_dir
        self._archives: list[Path] = []
        self._current_pixmap: QPixmap | None = None

        self.setWindowTitle(f"Archive — Scene {scene.number}: {scene.title}")
        self.resize(500, 400)

        # List of archived versions
        self._list_widget = QListWidget()
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)

        # Preview area
        self._preview_label = QLabel("Select an archived version to preview")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("color: #888; font-size: 13px;")
        self._preview_label.setMinimumHeight(200)

        # Buttons
        self._restore_btn = QPushButton("Restore")
        self._restore_btn.setEnabled(False)
        self._restore_btn.clicked.connect(self._on_restore)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self._restore_btn)
        btn_layout.addWidget(close_btn)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Archived versions of scene {scene.number}:"))
        layout.addWidget(self._list_widget, stretch=1)
        layout.addWidget(self._preview_label, stretch=2)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self._load_archives()

    def _load_archives(self) -> None:
        """Populate the list with archived versions."""
        self._archives = list_scene_archives(self._scene, self._output_dir)
        self._list_widget.clear()

        for archive_path in self._archives:
            ts = parse_archive_timestamp(archive_path)
            if ts:
                label = ts.strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                label = archive_path.name
            item = QListWidgetItem(label)
            self._list_widget.addItem(item)

    def _on_selection_changed(self, row: int) -> None:
        """Update preview and Restore button when selection changes."""
        self._restore_btn.setEnabled(0 <= row < len(self._archives))

        if 0 <= row < len(self._archives):
            archive_path = self._archives[row]
            pixmap = None
            if archive_path.exists():
                if self._scene.scene_type == "still":
                    pixmap = QPixmap(str(archive_path))
                    if pixmap.isNull():
                        pixmap = None
                else:
                    pixmap = _extract_thumbnail(archive_path)

            if pixmap is not None:
                self._current_pixmap = pixmap
                self._rescale_preview()
                return

            # Failed load — show filename
            self._current_pixmap = None
            self._preview_label.setText(archive_path.name)
        else:
            self._current_pixmap = None
            self._preview_label.clear()
            self._preview_label.setText("Select an archived version to preview")

    def _rescale_preview(self) -> None:
        """Scale the stored pixmap to fit the preview label's current size."""
        if self._current_pixmap is None:
            return
        scaled = self._current_pixmap.scaled(
            self._preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        """Rescale the preview image when the dialog is resized."""
        super().resizeEvent(event)
        self._rescale_preview()

    def _on_restore(self) -> None:
        """Restore the selected archive as the current output."""
        row = self._list_widget.currentRow()
        if row < 0 or row >= len(self._archives):
            return

        archive_path = self._archives[row]
        restore_archive(self._scene, archive_path, self._output_dir)

        # Refresh the list and accept the dialog
        self._load_archives()
        self.accept()

    @property
    def restored(self) -> bool:
        """Whether a restore was performed (dialog accepted)."""
        return self.result() == QDialog.DialogCode.Accepted
