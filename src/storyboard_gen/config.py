# ABOUTME: Configuration loader for storyboard-gen.
# ABOUTME: Reads project.yaml from current directory and .env for API credentials.

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from storyboard_gen.models import (
    VALID_ASPECT_RATIOS,
    VALID_BACKENDS,
    VALID_CAMERAS,
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

    subtitles_path = None
    subtitles_str = data.get("subtitles")
    if subtitles_str:
        subtitles_path = project_dir / subtitles_str

    style_reference = _parse_style_reference(data.get("style_reference"), project_dir)
    still_provider, clip_provider = _parse_providers(data.get("providers", {}))

    characters = _parse_characters(data.get("characters", {}), project_dir)
    scenes = _parse_scenes(data.get("scenes", []), characters, project_dir)

    return Project(
        title=title,
        aspect_ratio=aspect_ratio,
        style_prefix=style_prefix,
        characters=characters,
        scenes=scenes,
        style_reference=style_reference,
        still_provider=still_provider,
        clip_provider=clip_provider,
        audio=audio_path,
        subtitles=subtitles_path,
    )


def _parse_style_reference(raw, project_dir: Path) -> list[Path]:
    """Parse the top-level style_reference field.

    Args:
        raw: Raw value from YAML (None, list, or invalid).
        project_dir: Project directory for resolving relative paths.

    Returns:
        List of resolved Path objects (may be empty).

    Raises:
        ConfigError: If the value is not a list.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        raise ConfigError(
            "'style_reference' must be a list. "
            f'Change:\n  style_reference: "{raw}"\n'
            f"to:\n  style_reference:\n"
            f'    - "{raw}"'
        )
    if not isinstance(raw, list):
        raise ConfigError("'style_reference' must be a list")
    return [project_dir / r for r in raw]


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

    pricing = None
    raw_pricing = raw.get("pricing")
    if isinstance(raw_pricing, dict):
        unit_price = raw_pricing.get("unit_price")
        unit = raw_pricing.get("unit")
        if unit_price is not None and unit:
            pricing = {
                "unit_price": float(unit_price),
                "unit": str(unit),
                "currency": str(raw_pricing.get("currency", "USD")),
            }

    return ProviderConfig(
        backend=backend, model=model, options=options, pricing=pricing
    )


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

        ref_raw = char_data.get("reference")
        if ref_raw is not None:
            if isinstance(ref_raw, str):
                raise ConfigError(
                    f"Character '{char_id}': 'reference' must be a list "
                    f"since v0.29.0. "
                    f'Change:\n  reference: "{ref_raw}"\n'
                    f"to:\n  reference:\n"
                    f'    - "{ref_raw}"'
                )
            if not isinstance(ref_raw, list):
                raise ConfigError(f"Character '{char_id}': 'reference' must be a list")
            ref_paths = [project_dir / r for r in ref_raw]
        else:
            ref_paths = []

        characters[char_id] = Character(
            id=char_id,
            description=char_data.get("description", ""),
            reference=ref_paths,
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

        camera_raw = scene_data.get("camera")
        camera = camera_raw.upper() if isinstance(camera_raw, str) else camera_raw
        if camera not in VALID_CAMERAS:
            valid_names = sorted(v for v in VALID_CAMERAS if v is not None)
            raise ConfigError(
                f"Scene {i + 1}: invalid camera '{camera_raw}'. "
                f"Must be one of: {', '.join(valid_names)}"
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

        ref_raw = scene_data.get("reference")
        if ref_raw is not None:
            if isinstance(ref_raw, str):
                raise ConfigError(
                    f"Scene {i + 1}: 'reference' must be a list "
                    f"since v0.29.0. "
                    f'Change:\n  reference: "{ref_raw}"\n'
                    f"to:\n  reference:\n"
                    f'    - "{ref_raw}"'
                )
            if not isinstance(ref_raw, list):
                raise ConfigError(f"Scene {i + 1}: 'reference' must be a list")
            scene_reference = [project_dir / r for r in ref_raw]
        else:
            scene_reference = []

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
                camera=camera,
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
