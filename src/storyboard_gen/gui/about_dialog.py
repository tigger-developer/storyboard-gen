# ABOUTME: About dialog showing app name, version, description, and GitHub link.
# ABOUTME: Accessible from the toolbar About button.

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from storyboard_gen import __version__

GITHUB_URL = "https://github.com/tigger04/storyboard-gen"
MODELS_URL = f"{GITHUB_URL}/blob/master/docs/models.md"
AUTHOR_URL = "https://tigger.dev"


class AboutDialog(QDialog):
    """About dialog displaying app info and version."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("About storyboard-gen")
        self.setFixedWidth(400)

        layout = QVBoxLayout(self)

        self._name_label = QLabel("storyboard-gen")
        self._name_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(self._name_label)

        self._version_label = QLabel(f"Version {__version__}")
        layout.addWidget(self._version_label)

        self._description_label = QLabel(
            "Generate video storyboards from YAML using AI image and video APIs."
            " Supports multiple providers including Google Gemini, FAL.ai,"
            " and Replicate."
        )
        self._description_label.setWordWrap(True)
        layout.addWidget(self._description_label)

        self._link_label = QLabel(
            f'<a href="{GITHUB_URL}">GitHub</a>'
            f' · <a href="{MODELS_URL}">Supported Models</a>'
            f' · <a href="{AUTHOR_URL}">tigger.dev</a>'
        )
        self._link_label.setOpenExternalLinks(True)
        layout.addWidget(self._link_label)

        layout.addSpacing(12)

        self._button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)
