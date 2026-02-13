# ABOUTME: Orchestrator for image and video generation.
# ABOUTME: Delegates to provider implementations; handles archiving and post-processing.

import io
import logging
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image as PILImage

from storyboard_gen.models import Project, ProviderConfig, Scene
from storyboard_gen.providers import ImageProvider, create_provider
from storyboard_gen.providers.google import (
    DEFAULT_IMAGEN_MODEL,
    DEFAULT_VEO_MODEL,
)

logger = logging.getLogger(__name__)


def _resolve_provider(scene: Scene, project: Project, scene_type: str) -> ImageProvider:
    """Resolve the provider for a scene, checking overrides then project defaults.

    Falls back to Google with default models if no provider is configured.
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
    logger.info("Generating still for scene %d: %s", scene.number, scene.title)
    logger.debug("Prompt: %s", full_prompt)

    reference_images = project.get_reference_images(scene)
    output_path = stills_dir / f"scene_{scene.number:02d}.png"

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

    logger.info("Saved scene %d (%s) -> %s", scene.number, scene.title, output_path)
    return output_path


def generate_clip(
    scene: Scene,
    project: Project,
    output_dir: Path,
    provider: ImageProvider | None = None,
) -> Path:
    """Generate a video clip for a scene.

    Args:
        scene: The scene to generate.
        project: The project containing style prefix and characters.
        output_dir: Base output directory for the project.
        provider: Optional pre-created provider (for testing).

    Returns:
        Path to the saved MP4 file.

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
    logger.info("Generating clip for scene %d: %s", scene.number, scene.title)
    logger.debug("Prompt: %s", full_prompt)

    reference_images = project.get_reference_images(scene)
    output_path = clips_dir / f"scene_{scene.number:02d}.mp4"

    video_bytes = provider.generate_clip(
        prompt=full_prompt,
        output_path=output_path,
        aspect_ratio=project.aspect_ratio,
        duration=scene.duration,
        reference_images=reference_images or None,
        options=provider.options,
    )

    _archive_existing(output_path)
    output_path.write_bytes(video_bytes)

    logger.info("Saved scene %d (%s) -> %s", scene.number, scene.title, output_path)
    return output_path
