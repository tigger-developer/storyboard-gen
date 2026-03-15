# ABOUTME: Dialog for editing .env provider credentials (API keys, buckets, etc.).
# ABOUTME: Reads/writes the project .env file with grouped fields per provider.

from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

# Ordered groups of .env keys, displayed as labelled sections.
_ENV_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Google (Gemini Developer API)",
        [
            ("GEMINI_API_KEY", "API Key"),
        ],
    ),
    (
        "Google (Vertex AI)",
        [
            ("USE_VERTEX", "Use Vertex (true/false)"),
            ("GOOGLE_CLOUD_PROJECT", "Cloud Project"),
            ("GOOGLE_CLOUD_LOCATION", "Cloud Location"),
            ("GCS_OUTPUT_BUCKET", "GCS Output Bucket"),
        ],
    ),
    (
        "FAL.ai",
        [
            ("FAL_KEY", "API Key"),
        ],
    ),
    (
        "Replicate",
        [
            ("REPLICATE_API_TOKEN", "API Token"),
        ],
    ),
]


def _parse_env(text: str) -> dict[str, str]:
    """Parse .env content into a dict of active (uncommented) key=value pairs."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            result[key.strip()] = value.strip()
    return result


class EnvEditorDialog(QDialog):
    """Dialog for editing .env provider credentials."""

    def __init__(self, env_path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Provider Configuration")
        self.setMinimumWidth(450)
        self._env_path = env_path
        self._fields: dict[str, QLineEdit] = {}

        # Load existing values
        if env_path.exists():
            values = _parse_env(env_path.read_text())
        else:
            values = {}

        layout = QVBoxLayout(self)

        # Monospace font for API keys and credentials (#119)
        mono_font = QFont("Menlo, Consolas, monospace")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)

        for group_name, keys in _ENV_GROUPS:
            group = QGroupBox(group_name)
            form = QFormLayout()
            for env_key, label in keys:
                field = QLineEdit()
                field.setFont(mono_font)
                field.setMinimumWidth(400)
                field.setText(values.get(env_key, ""))
                field.setPlaceholderText(f"Enter {label.lower()}")
                form.addRow(f"{label}:", field)
                self._fields[env_key] = field
            group.setLayout(form)
            layout.addWidget(group)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._save)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _save(self) -> None:
        """Write field values back to the .env file.

        Active values are written as KEY=value. Empty fields are
        written as commented-out lines (# KEY=) to preserve the
        key as a placeholder.
        """
        lines: list[str] = []
        for _group_name, keys in _ENV_GROUPS:
            for env_key, _label in keys:
                value = self._fields[env_key].text().strip()
                if value:
                    lines.append(f"{env_key}={value}")
                else:
                    lines.append(f"# {env_key}=")
            lines.append("")  # blank line between groups
        self._env_path.write_text("\n".join(lines))
