# ABOUTME: Configuration loader for storyboard-gen.
# ABOUTME: Reads project.yaml from current directory and .env for API credentials.

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from storyboard_gen.models import (
    VALID_ASPECT_RATIOS,
    VALID_BACKENDS,
    VALID_KEN_BURNS,
    VALID_SCENE_TYPES,
    Character,
    Project,
    ProviderConfig,
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

    audio_path = None
    audio_str = data.get("audio")
    if audio_str:
        audio_path = project_dir / audio_str

    still_provider, clip_provider = _parse_providers(data.get("providers", {}))

    characters = _parse_characters(data.get("characters", {}), project_dir)
    scenes = _parse_scenes(data.get("scenes", []), characters, project_dir)

    return Project(
        title=title,
        aspect_ratio=aspect_ratio,
        style_prefix=style_prefix,
        characters=characters,
        scenes=scenes,
        still_provider=still_provider,
        clip_provider=clip_provider,
        audio=audio_path,
    )


def _parse_provider_config(raw: dict, context: str) -> ProviderConfig:
    """Parse a single provider config dict into a ProviderConfig."""
    backend = raw.get("backend", "")
    if backend not in VALID_BACKENDS:
        raise ConfigError(
            f"Invalid provider backend '{backend}' in {context}. "
            f"Must be one of: {', '.join(sorted(VALID_BACKENDS))}"
        )
    model = raw.get("model", "")
    options = raw.get("options", {})
    if not isinstance(options, dict):
        options = {}
    return ProviderConfig(backend=backend, model=model, options=options)


def _parse_providers(
    raw: dict,
) -> tuple[ProviderConfig | None, ProviderConfig | None]:
    """Parse the top-level providers section.

    Returns (still_provider, clip_provider), either of which may be None.
    """
    if not raw or not isinstance(raw, dict):
        return None, None

    still_provider = None
    clip_provider = None

    if "still" in raw and isinstance(raw["still"], dict):
        still_provider = _parse_provider_config(raw["still"], "providers.still")
    if "clip" in raw and isinstance(raw["clip"], dict):
        clip_provider = _parse_provider_config(raw["clip"], "providers.clip")

    return still_provider, clip_provider


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


def _parse_scenes(
    raw: list, characters: dict[str, Character], project_dir: Path
) -> list[Scene]:
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

        scene_provider = None
        raw_provider = scene_data.get("provider")
        if isinstance(raw_provider, dict):
            scene_provider = _parse_provider_config(
                raw_provider, f"scene {i + 1} provider"
            )

        scene_model = scene_data.get("model")

        if scene_model and scene_provider:
            raise ConfigError(
                f"Scene {i + 1}: cannot specify both 'model' and 'provider'"
            )

        scene_reference = None
        ref_str = scene_data.get("reference")
        if ref_str:
            scene_reference = project_dir / ref_str

        # Veo 3.1 clip generation fields
        source_frame = None
        source_frame_str = scene_data.get("source_frame")
        if source_frame_str:
            if scene_type != "clip":
                raise ConfigError(
                    f"Scene {i + 1}: source_frame is only valid on clip scenes"
                )
            source_frame = project_dir / source_frame_str

        last_frame = None
        last_frame_str = scene_data.get("last_frame")
        if last_frame_str:
            if scene_type != "clip":
                raise ConfigError(
                    f"Scene {i + 1}: last_frame is only valid on clip scenes"
                )
            if not source_frame_str:
                raise ConfigError(
                    f"Scene {i + 1}: last_frame requires source_frame to be set"
                )
            last_frame = project_dir / last_frame_str

        extend_from = None
        extend_from_raw = scene_data.get("extend_from")
        if extend_from_raw is not None:
            if scene_type != "clip":
                raise ConfigError(
                    f"Scene {i + 1}: extend_from is only valid on clip scenes"
                )
            if source_frame_str:
                raise ConfigError(
                    f"Scene {i + 1}: extend_from and source_frame are "
                    f"mutually exclusive"
                )
            extend_from = str(extend_from_raw)

        seed = None
        seed_raw = scene_data.get("seed")
        if seed_raw is not None:
            seed = int(seed_raw)

        variants = 1
        variants_raw = scene_data.get("variants")
        if variants_raw is not None:
            variants = int(variants_raw)
            if variants < 1 or variants > 4:
                raise ConfigError(
                    f"Scene {i + 1}: variants must be between 1 and 4, got {variants}"
                )

        scenes.append(
            Scene(
                number=str(scene_data.get("number", i + 1)),
                title=scene_data.get("title", f"Scene {i + 1}"),
                scene_type=scene_type,
                prompt=scene_data.get("prompt", ""),
                duration=float(scene_data.get("duration", 5)),
                camera=scene_data.get("camera"),
                ken_burns=ken_burns,
                characters=char_ids,
                provider=scene_provider,
                model=scene_model,
                reference=scene_reference,
                source_frame=source_frame,
                last_frame=last_frame,
                extend_from=extend_from,
                seed=seed,
                variants=variants,
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
