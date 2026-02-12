# ABOUTME: Configuration loader for storyboard-gen.
# ABOUTME: Reads project.yaml from current directory and .env for API credentials.

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from storyboard_gen.models import (
    VALID_ASPECT_RATIOS,
    VALID_KEN_BURNS,
    VALID_SCENE_TYPES,
    Character,
    Project,
    Scene,
)


class ConfigError(Exception):
    """Raised when project.yaml is missing or invalid."""


def load_project(project_dir: Path | None = None) -> Project:
    """Load a Project from project.yaml in the given directory.

    Args:
        project_dir: Directory containing project.yaml. Defaults to cwd.

    Returns:
        A validated Project instance.

    Raises:
        ConfigError: If project.yaml is missing or invalid.
    """
    if project_dir is None:
        project_dir = Path.cwd()

    yaml_path = project_dir / "project.yaml"
    if not yaml_path.exists():
        raise ConfigError(f"No project.yaml found in {project_dir}")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ConfigError("project.yaml must be a YAML mapping")

    return _parse_project(data, project_dir)


def _parse_project(data: dict, project_dir: Path) -> Project:
    """Parse raw YAML data into a validated Project."""
    title = data.get("title")
    if not title:
        raise ConfigError("project.yaml must have a 'title'")

    aspect_ratio = data.get("aspect_ratio", "16:9")
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise ConfigError(
            f"Invalid aspect_ratio '{aspect_ratio}'. "
            f"Must be one of: {', '.join(sorted(VALID_ASPECT_RATIOS))}"
        )

    style_prefix = data.get("style_prefix", "")

    characters = _parse_characters(data.get("characters", {}), project_dir)
    scenes = _parse_scenes(data.get("scenes", []), characters)

    return Project(
        title=title,
        aspect_ratio=aspect_ratio,
        style_prefix=style_prefix,
        characters=characters,
        scenes=scenes,
    )


def _parse_characters(raw: dict, project_dir: Path) -> dict[str, Character]:
    """Parse the characters section of project.yaml."""
    characters = {}
    for char_id, char_data in raw.items():
        if not isinstance(char_data, dict):
            raise ConfigError(f"Character '{char_id}' must be a mapping")

        ref_path = None
        ref_str = char_data.get("reference")
        if ref_str:
            ref_path = project_dir / ref_str
            # Don't raise if missing — warn at generation time

        characters[char_id] = Character(
            id=char_id,
            description=char_data.get("description", ""),
            reference=ref_path,
        )
    return characters


def _parse_scenes(raw: list, characters: dict[str, Character]) -> list[Scene]:
    """Parse the scenes section of project.yaml."""
    if not raw:
        raise ConfigError("project.yaml must have at least one scene")

    scenes = []
    for i, scene_data in enumerate(raw):
        if not isinstance(scene_data, dict):
            raise ConfigError(f"Scene {i + 1} must be a mapping")

        scene_type = scene_data.get("type", "still")
        if scene_type not in VALID_SCENE_TYPES:
            raise ConfigError(
                f"Scene {i + 1}: invalid type '{scene_type}'. "
                f"Must be one of: {', '.join(sorted(VALID_SCENE_TYPES))}"
            )

        ken_burns = scene_data.get("ken_burns")
        if ken_burns not in VALID_KEN_BURNS:
            raise ConfigError(
                f"Scene {i + 1}: invalid ken_burns '{ken_burns}'. "
                f"Must be one of: {', '.join(str(v) for v in sorted(VALID_KEN_BURNS, key=str))}"
            )

        char_ids = scene_data.get("characters", [])
        for cid in char_ids:
            if cid not in characters:
                raise ConfigError(
                    f"Scene {i + 1}: references unknown character '{cid}'"
                )

        scenes.append(
            Scene(
                number=scene_data.get("number", i + 1),
                title=scene_data.get("title", f"Scene {i + 1}"),
                scene_type=scene_type,
                prompt=scene_data.get("prompt", ""),
                duration=scene_data.get("duration", 5),
                camera=scene_data.get("camera"),
                ken_burns=ken_burns,
                characters=char_ids,
            )
        )

    return scenes


def get_env_config() -> dict:
    """Load API configuration from environment variables.

    Looks for .env in the current directory first, then falls back
    to environment variables.
    """
    load_dotenv(Path.cwd() / ".env")

    use_vertex = os.environ.get("USE_VERTEX", "false").lower() == "true"

    return {
        "use_vertex": use_vertex,
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT"),
        "location": os.environ.get("GOOGLE_CLOUD_LOCATION"),
        "api_key": os.environ.get("GEMINI_API_KEY"),
        "gcs_bucket": os.environ.get("GCS_OUTPUT_BUCKET"),
    }
