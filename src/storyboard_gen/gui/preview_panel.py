# ABOUTME: Preview panel widget for storyboard-gen GUI.
# ABOUTME: Displays generated still images and clip file info with placeholder for pending scenes.

import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QStackedLayout, QVBoxLayout, QWidget


def _format_file_size(size_bytes: int) -> str:
    """Format a file size in bytes to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


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


class PreviewPanel(QWidget):
    """Panel that displays a preview of a generated still image or clip info.

    Shows a placeholder message when no scene is selected.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.placeholder_label = QLabel("No scene selected")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #888; font-size: 14px;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)

        # Clip info widget — thumbnail + file details
        self._clip_widget = QWidget()
        clip_layout = QVBoxLayout()
        clip_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.clip_thumbnail_label = QLabel()
        self.clip_thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clip_layout.addWidget(self.clip_thumbnail_label)

        self.clip_info_label = QLabel()
        self.clip_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clip_info_label.setStyleSheet("color: #ccc; font-size: 13px;")
        clip_layout.addWidget(self.clip_info_label)

        self._clip_widget.setLayout(clip_layout)

        self._layout = QStackedLayout()
        self._layout.addWidget(self.placeholder_label)
        self._layout.addWidget(self.image_label)
        self._layout.addWidget(self._clip_widget)
        self._layout.setCurrentWidget(self.placeholder_label)
        self.setLayout(self._layout)

    def load_image(self, image_path: Path) -> None:
        """Load and display an image from the given path.

        Args:
            image_path: Path to a PNG or other image file.
        """
        if not image_path.exists():
            self.clear_image()
            return

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self.clear_image()
            return

        # Scale to fit the panel while maintaining aspect ratio
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self._layout.setCurrentWidget(self.image_label)

    def show_clip_info(self, clip_path: Path) -> None:
        """Display clip file information and thumbnail.

        Args:
            clip_path: Path to a video clip file.
        """
        if not clip_path.exists():
            self.clear_image()
            return

        # Try to extract a thumbnail
        thumbnail = _extract_thumbnail(clip_path)
        if thumbnail:
            scaled = thumbnail.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.clip_thumbnail_label.setPixmap(scaled)
        else:
            self.clip_thumbnail_label.setText("[ Video clip ]")
            self.clip_thumbnail_label.setStyleSheet(
                "color: #aaa; font-size: 18px; padding: 40px;"
            )

        # File info
        size = _format_file_size(clip_path.stat().st_size)
        self.clip_info_label.setText(f"{clip_path.name}  ({size})")

        self._layout.setCurrentWidget(self._clip_widget)

    def clear_image(self) -> None:
        """Reset to the placeholder view."""
        self.image_label.clear()
        self.clip_thumbnail_label.clear()
        self.clip_info_label.clear()
        self._layout.setCurrentWidget(self.placeholder_label)
