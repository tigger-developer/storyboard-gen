# ABOUTME: Orchestrator for image and video generation.
# ABOUTME: Delegates to provider implementations; handles archiving and post-processing.

import io
import logging
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image as PILImage

from storyboard_gen.models import Project, ProviderConfig, Scene, format_scene_number
from storyboard_gen.providers import ImageProvider, create_provider
from storyboard_gen.providers.google import (
    DEFAULT_IMAGEN_MODEL,
    DEFAULT_VEO_MODEL,
)

logger = logging.getLogger(__name__)


def resolve_provider_config(
    scene: Scene, project: Project, scene_type: str
) -> ProviderConfig:
    """Resolve the provider config for a scene without instantiating it.

    Checks per-scene overrides, then project defaults, then Google defaults.
    Returns a ProviderConfig that can be inspected (dry-run) or instantiated.
    """
    # Per-scene full provider override takes precedence
    provider_cfg = scene.provider

    # Per-scene model-only override: merge with project-level or Google default
    if provider_cfg is None and scene.model:
        if scene_type == "still":
            base = project.still_provider
        else:
            base = project.clip_provider

        if base is None:
            default_model = (
                DEFAULT_IMAGEN_MODEL if scene_type == "still" else DEFAULT_VEO_MODEL
            )
            base = ProviderConfig(backend="google", model=default_model)

        provider_cfg = ProviderConfig(
            backend=base.backend,
            model=scene.model,
            options=base.options,
        )

    # Then project-level config
    if provider_cfg is None:
        if scene_type == "still":
            provider_cfg = project.still_provider
        else:
            provider_cfg = project.clip_provider

    # Default to Google if nothing configured
    if provider_cfg is None:
        if scene_type == "still":
            provider_cfg = ProviderConfig(backend="google", model=DEFAULT_IMAGEN_MODEL)
        else:
            provider_cfg = ProviderConfig(backend="google", model=DEFAULT_VEO_MODEL)

    return provider_cfg


def _resolve_provider(scene: Scene, project: Project, scene_type: str) -> ImageProvider:
    """Resolve and instantiate the provider for a scene."""
    provider_cfg = resolve_provider_config(scene, project, scene_type)
    return create_provider(
        backend=provider_cfg.backend,
        model=provider_cfg.model,
        options=provider_cfg.options,
    )


def crop_to_aspect_ratio(img: PILImage.Image, aspect_ratio: str) -> PILImage.Image:
    """Centre-crop an image to the target aspect ratio.

    The edit_image API sometimes ignores the requested aspect ratio,
    returning landscape when portrait was requested. This function
    crops the image to match, preserving the larger dimension where
    possible.

    Args:
        img: Source PIL Image.
        aspect_ratio: Target ratio as "W:H" string (e.g. "9:16").

    Returns:
        Cropped PIL Image matching the target aspect ratio.
    """
    target_w, target_h = (int(x) for x in aspect_ratio.split(":"))
    target_ratio = target_w / target_h

    src_w, src_h = img.size
    src_ratio = src_w / src_h

    if abs(src_ratio - target_ratio) < 0.01:
        return img

    if src_ratio > target_ratio:
        # Too wide — crop width, keep height
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        return img.crop((left, 0, left + new_w, src_h))
    else:
        # Too tall — crop height, keep width
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        return img.crop((0, top, src_w, top + new_h))


def _archive_existing(output_path: Path) -> None:
    """Move an existing file to an archive directory with a timestamp."""
    if not output_path.exists():
        return
    archive_dir = output_path.parent / "archive"
    archive_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = output_path.stem
    archive_path = archive_dir / f"{stem}_{timestamp}{output_path.suffix}"
    output_path.rename(archive_path)
    logger.info("Archived previous file -> %s", archive_path)


def generate_still(
    scene: Scene,
    project: Project,
    output_dir: Path,
    provider: ImageProvider | None = None,
) -> Path:
    """Generate a still image for a scene.

    Resolves the appropriate provider, gathers reference images,
    delegates generation, then handles archiving and aspect ratio
    post-processing.

    Args:
        scene: The scene to generate.
        project: The project containing style prefix and characters.
        output_dir: Base output directory for the project.
        provider: Optional pre-created provider (for testing).

    Returns:
        Path to the saved PNG file.

    Raises:
        ValueError: If the scene is not a still type.
        RuntimeError: If the API returns no images.
    """
    if scene.scene_type != "still":
        raise ValueError(
            f"Scene {scene.number} is type '{scene.scene_type}', not 'still'"
        )

    if provider is None:
        provider = _resolve_provider(scene, project, "still")

    stills_dir = output_dir / "stills"
    stills_dir.mkdir(parents=True, exist_ok=True)

    full_prompt = project.build_prompt(scene)
    logger.info("Generating still for scene %s: %s", scene.number, scene.title)
    logger.debug("Prompt: %s", full_prompt)

    reference_images = project.get_reference_images(scene)
    output_path = stills_dir / f"scene_{format_scene_number(scene.number)}.png"

    image_bytes = provider.generate_still(
        prompt=full_prompt,
        output_path=output_path,
        aspect_ratio=project.aspect_ratio,
        reference_images=reference_images or None,
        options=provider.options,
    )

    # Post-process: ensure aspect ratio is correct
    img = PILImage.open(io.BytesIO(image_bytes))
    img = crop_to_aspect_ratio(img, project.aspect_ratio)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    _archive_existing(output_path)
    output_path.write_bytes(image_bytes)

    logger.info("Saved scene %s (%s) -> %s", scene.number, scene.title, output_path)
    return output_path


def _resolve_extend_from(scene: Scene, output_dir: Path) -> Path | None:
    """Resolve extend_from scene number to an actual .mp4 path.

    Checks clips/ first, then intermediate/. Returns None if extend_from
    is not set on the scene.

    Raises:
        RuntimeError: If extend_from is set but the source clip is not found.
    """
    if scene.extend_from is None:
        return None

    scene_num = format_scene_number(scene.extend_from)
    filename = f"scene_{scene_num}.mp4"

    clips_path = output_dir / "clips" / filename
    if clips_path.exists():
        return clips_path

    intermediate_path = output_dir / "intermediate" / filename
    if intermediate_path.exists():
        return intermediate_path

    raise RuntimeError(
        f"Cannot extend from scene {scene.extend_from}: "
        f"no clip found at {clips_path} or {intermediate_path}. "
        f"Generate that scene first."
    )


def generate_clip(
    scene: Scene,
    project: Project,
    output_dir: Path,
    provider: ImageProvider | None = None,
    project_dir: Path | None = None,
) -> Path:
    """Generate a video clip for a scene.

    Args:
        scene: The scene to generate.
        project: The project containing style prefix and characters.
        output_dir: Base output directory for the project.
        provider: Optional pre-created provider (for testing).
        project_dir: Project root directory for operation logging.

    Returns:
        Path to the saved MP4 file (first variant if multiple).

    Raises:
        ValueError: If the scene is not a clip type.
        RuntimeError: If generation fails or times out.
    """
    if scene.scene_type != "clip":
        raise ValueError(
            f"Scene {scene.number} is type '{scene.scene_type}', not 'clip'"
        )

    if provider is None:
        provider = _resolve_provider(scene, project, "clip")

    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    full_prompt = project.build_prompt(scene)
    logger.info("Generating clip for scene %s: %s", scene.number, scene.title)
    logger.debug("Prompt: %s", full_prompt)

    reference_images = project.get_reference_images(scene)
    scene_num = format_scene_number(scene.number)

    # Resolve extend_from to an actual video path
    extend_from_video = _resolve_extend_from(scene, output_dir)

    # Resolve scene characters to Character objects (#37)
    scene_characters = [
        project.characters[cid] for cid in scene.characters if cid in project.characters
    ]

    gen_kwargs = {
        "prompt": full_prompt,
        "output_path": clips_dir / f"scene_{scene_num}.mp4",
        "aspect_ratio": project.aspect_ratio,
        "duration": scene.duration,
        "reference_images": reference_images or None,
        "options": provider.options,
        "source_frame": scene.source_frame,
        "last_frame": scene.last_frame,
        "extend_from_video": extend_from_video,
        "seed": scene.seed,
        "number_of_videos": scene.variants,
        "scene_characters": scene_characters or None,
    }
    if project_dir is not None:
        gen_kwargs["project_dir"] = project_dir
        gen_kwargs["scene_number"] = scene.number

    video_bytes_list = provider.generate_clip(**gen_kwargs)

    if scene.variants > 1:
        # Archive existing variant files and bare file
        bare_path = clips_dir / f"scene_{scene_num}.mp4"
        _archive_existing(bare_path)
        for vi in range(4):
            variant_path = clips_dir / f"scene_{scene_num}_v{vi}.mp4"
            _archive_existing(variant_path)

        # Save variant files
        first_path = None
        for vi, vb in enumerate(video_bytes_list):
            variant_path = clips_dir / f"scene_{scene_num}_v{vi}.mp4"
            variant_path.write_bytes(vb)
            logger.info(
                "Saved variant %d for scene %s -> %s", vi, scene.number, variant_path
            )
            if first_path is None:
                first_path = variant_path
        return first_path
    else:
        # Single variant — save as bare file (existing behaviour)
        output_path = clips_dir / f"scene_{scene_num}.mp4"
        _archive_existing(output_path)
        output_path.write_bytes(video_bytes_list[0])
        logger.info("Saved scene %s (%s) -> %s", scene.number, scene.title, output_path)
        return output_path
