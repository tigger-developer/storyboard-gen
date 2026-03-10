# ABOUTME: Persistent GUI settings backed by QSettings.
# ABOUTME: Stores editor font size, last project path, and last browsed directory.

from PySide6.QtCore import QSettings

DEFAULTS = {
    "editor/font_size": 11,
    "session/last_project": "",
    "session/last_directory": "",
}

MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 32


class AppSettings:
    """Persistent GUI settings backed by QSettings.

    On macOS this writes to ~/Library/Preferences/com.storyboard-gen.plist.
    On Linux it writes to ~/.config/storyboard-gen/storyboard-gen.conf.
    """

    def __init__(self):
        self._qs = QSettings("storyboard-gen", "storyboard-gen")

    @property
    def editor_font_size(self) -> int:
        """The YAML editor font size in points (8–32)."""
        return int(self._qs.value("editor/font_size", DEFAULTS["editor/font_size"]))

    @editor_font_size.setter
    def editor_font_size(self, size: int) -> None:
        self._qs.setValue(
            "editor/font_size", max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
        )

    @property
    def last_project(self) -> str:
        """The last opened project directory path."""
        return str(
            self._qs.value("session/last_project", DEFAULTS["session/last_project"])
        )

    @last_project.setter
    def last_project(self, path: str) -> None:
        self._qs.setValue("session/last_project", path)

    @property
    def last_directory(self) -> str:
        """The last browsed directory in the Open Project dialog."""
        return str(
            self._qs.value("session/last_directory", DEFAULTS["session/last_directory"])
        )

    @last_directory.setter
    def last_directory(self, path: str) -> None:
        self._qs.setValue("session/last_directory", path)
