# ABOUTME: Shared test fixtures for storyboard-gen.
# ABOUTME: Provides sample project.yaml data and temporary directories.

from pathlib import Path

import pytest
import yaml


SAMPLE_PROJECT_YAML = {
    "title": "Test Project",
    "aspect_ratio": "9:16",
    "style_prefix": "Watercolour illustration style. Soft lines.",
    "characters": {
        "hero": {
            "description": "A young boy with red hair",
            "reference": "references/hero.png",
        },
        "sidekick": {
            "description": "A tall woman in a blue coat",
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
            "prompt": "A boy stands on a hill looking at the sea.",
            "characters": ["hero"],
        },
        {
            "number": 2,
            "title": "The meeting",
            "type": "still",
            "duration": 4,
            "camera": "CLOSE",
            "ken_burns": "static",
            "prompt": "The boy meets a tall woman.",
            "characters": ["hero", "sidekick"],
        },
        {
            "number": 3,
            "title": "The chase",
            "type": "clip",
            "duration": 6,
            "prompt": "They run through a field.",
            "characters": ["hero", "sidekick"],
        },
    ],
}


@pytest.fixture
def sample_project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with a valid project.yaml."""
    yaml_path = tmp_path / "project.yaml"
    yaml_path.write_text(yaml.dump(SAMPLE_PROJECT_YAML))

    refs_dir = tmp_path / "references"
    refs_dir.mkdir()
    # Create a dummy reference image
    (refs_dir / "hero.png").write_bytes(b"fake-png-data")

    return tmp_path


@pytest.fixture
def minimal_project_yaml(tmp_path: Path) -> Path:
    """Create a minimal valid project.yaml."""
    data = {
        "title": "Minimal",
        "scenes": [
            {
                "number": 1,
                "title": "Only scene",
                "type": "still",
                "duration": 3,
                "prompt": "A blank canvas.",
            }
        ],
    }
    yaml_path = tmp_path / "project.yaml"
    yaml_path.write_text(yaml.dump(data))
    return tmp_path
