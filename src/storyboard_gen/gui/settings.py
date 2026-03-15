# ABOUTME: Persistent GUI settings backed by QSettings.
# ABOUTME: Stores editor font size, last project path, window layout, and last browsed directory.

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

    # --- Window layout persistence ---

    @property
    def window_geometry(self) -> bytes | None:
        """Saved window geometry (position, size, maximized state)."""
        val = self._qs.value("window/geometry")
        if val is None:
            return None
        return bytes(val)

    @window_geometry.setter
    def window_geometry(self, data: bytes) -> None:
        self._qs.setValue("window/geometry", data)

    @property
    def main_splitter_state(self) -> bytes | None:
        """Saved main (vertical) splitter state."""
        val = self._qs.value("window/main_splitter")
        if val is None:
            return None
        return bytes(val)

    @main_splitter_state.setter
    def main_splitter_state(self, data: bytes) -> None:
        self._qs.setValue("window/main_splitter", data)

    @property
    def content_splitter_state(self) -> bytes | None:
        """Saved content (horizontal) splitter state."""
        val = self._qs.value("window/content_splitter")
        if val is None:
            return None
        return bytes(val)

    @content_splitter_state.setter
    def content_splitter_state(self, data: bytes) -> None:
        self._qs.setValue("window/content_splitter", data)

    @property
    def console_visible(self) -> bool:
        """Whether the console panel was visible when the window was last closed."""
        val = self._qs.value("window/console_visible", False)
        # QSettings may return string "true"/"false" on some platforms
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @console_visible.setter
    def console_visible(self, visible: bool) -> None:
        self._qs.setValue("window/console_visible", visible)

    @property
    def yaml_editor_visible(self) -> bool:
        """Whether the YAML editor pane was visible when the window was last closed."""
        val = self._qs.value("window/yaml_editor_visible", False)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @yaml_editor_visible.setter
    def yaml_editor_visible(self, visible: bool) -> None:
        self._qs.setValue("window/yaml_editor_visible", visible)
