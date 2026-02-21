# ABOUTME: Image preview panel widget for storyboard-gen GUI.
# ABOUTME: Displays generated still images with placeholder for pending scenes.

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QStackedLayout, QWidget


class PreviewPanel(QWidget):
    """Panel that displays a preview of a generated still image.

    Shows a placeholder message when no image is loaded.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.placeholder_label = QLabel("No scene selected")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #888; font-size: 14px;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)

        self._layout = QStackedLayout()
        self._layout.addWidget(self.placeholder_label)
        self._layout.addWidget(self.image_label)
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

    def clear_image(self) -> None:
        """Reset to the placeholder view."""
        self.image_label.clear()
        self._layout.setCurrentWidget(self.placeholder_label)
