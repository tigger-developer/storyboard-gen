# ABOUTME: Image and video generation for storyboard-gen.
# ABOUTME: Calls Imagen for stills and Veo for clips via Google GenAI SDK.

import io
import logging
import time
from pathlib import Path

from google.genai import types
from PIL import Image as PILImage

from storyboard_gen.client import create_client
from storyboard_gen.models import Project, Scene

logger = logging.getLogger(__name__)

IMAGEN_MODEL = "imagen-4.0-generate-001"
IMAGEN_CAPABILITY_MODEL = "imagen-3.0-capability-001"
VEO_MODEL = "veo-3.1-fast-generate-001"


def _build_subject_references(
    project: Project, scene: Scene
) -> list[types.SubjectReferenceImage]:
    """Build SubjectReferenceImage list from scene's character references.

    Only includes characters that have a reference image file on disk.
    Each reference gets a sequential reference_id starting at 1.
    """
    ref_images = []
    ref_id = 1
    for char_id in scene.characters:
        char = project.characters.get(char_id)
        if char and char.reference and char.reference.exists():
            ref_images.append(
                types.SubjectReferenceImage(
                    reference_id=ref_id,
                    reference_image=types.Image.from_file(location=str(char.reference)),
                    config=types.SubjectReferenceConfig(
                        subject_type="SUBJECT_TYPE_PERSON",
                        subject_description=char.description.strip(),
                    ),
                )
            )
            logger.info("Reference [%d] for '%s': %s", ref_id, char_id, char.reference)
            ref_id += 1
    return ref_images


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


def generate_still(
    scene: Scene,
    project: Project,
    output_dir: Path,
    client: object | None = None,
) -> Path:
    """Generate a still image for a scene.

    When character reference images are available, uses edit_image with
    SubjectReferenceImage on imagen-3.0-capability-001 for character
    consistency. Falls back to generate_images on imagen-4.0 otherwise.

    Args:
        scene: The scene to generate.
        project: The project containing style prefix and characters.
        output_dir: Base output directory for the project.
        client: Optional pre-created GenAI client (for testing).

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

    if client is None:
        client = create_client()

    stills_dir = output_dir / "stills"
    stills_dir.mkdir(parents=True, exist_ok=True)

    full_prompt = project.build_prompt(scene)
    logger.info("Generating still for scene %d: %s", scene.number, scene.title)
    logger.debug("Prompt: %s", full_prompt)

    # Only use subject references for single-character scenes to avoid
    # reference bleeding (one character's traits applied to another).
    use_references = len(scene.characters) == 1
    ref_images = _build_subject_references(project, scene) if use_references else []

    if ref_images:
        logger.info(
            "Using edit_image with %d reference(s) on %s",
            len(ref_images),
            IMAGEN_CAPABILITY_MODEL,
        )
        response = client.models.edit_image(
            model=IMAGEN_CAPABILITY_MODEL,
            prompt=full_prompt,
            reference_images=ref_images,
            config=types.EditImageConfig(
                number_of_images=1,
                aspect_ratio=project.aspect_ratio,
            ),
        )
    else:
        response = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=full_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=project.aspect_ratio,
            ),
        )

    if not response.generated_images:
        raise RuntimeError(f"No image generated for scene {scene.number}")

    image_bytes = response.generated_images[0].image.image_bytes

    # edit_image may ignore aspect_ratio — crop to match if needed.
    if ref_images:
        img = PILImage.open(io.BytesIO(image_bytes))
        img = crop_to_aspect_ratio(img, project.aspect_ratio)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

    output_path = stills_dir / f"scene_{scene.number:02d}.png"
    output_path.write_bytes(image_bytes)

    logger.info("Saved scene %d (%s) -> %s", scene.number, scene.title, output_path)
    return output_path


def generate_clip(
    scene: Scene,
    project: Project,
    output_dir: Path,
    client: object | None = None,
    poll_interval: int = 10,
    max_wait: int = 600,
) -> Path:
    """Generate a video clip for a scene.

    Veo is a long-running operation. This function submits the request
    and polls until completion or timeout.

    Args:
        scene: The scene to generate.
        project: The project containing style prefix and characters.
        output_dir: Base output directory for the project.
        client: Optional pre-created GenAI client.
        poll_interval: Seconds between status checks.
        max_wait: Maximum seconds to wait before timeout.

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

    if client is None:
        client = create_client()

    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    full_prompt = project.build_prompt(scene)
    logger.info("Generating clip for scene %d: %s", scene.number, scene.title)
    logger.debug("Prompt: %s", full_prompt)

    operation = client.models.generate_videos(
        model=VEO_MODEL,
        prompt=full_prompt,
    )

    elapsed = 0
    while not operation.done:
        if elapsed >= max_wait:
            raise RuntimeError(
                f"Scene {scene.number}: video generation timed out after {max_wait}s"
            )
        logger.info(
            "Scene %d: waiting for video generation (%ds elapsed)...",
            scene.number,
            elapsed,
        )
        time.sleep(poll_interval)
        elapsed += poll_interval

    if not operation.result or not operation.result.generated_videos:
        raise RuntimeError(f"No video generated for scene {scene.number}")

    video = operation.result.generated_videos[0]
    output_path = clips_dir / f"scene_{scene.number:02d}.mp4"

    # Veo returns video bytes directly or via URI depending on backend
    if hasattr(video, "video") and hasattr(video.video, "video_bytes"):
        output_path.write_bytes(video.video.video_bytes)
    elif hasattr(video, "video") and hasattr(video.video, "uri"):
        logger.info("Downloading from %s", video.video.uri)
        # GCS download handled by the SDK or gsutil
        _download_gcs(video.video.uri, output_path)
    else:
        raise RuntimeError(f"Scene {scene.number}: unexpected video response format")

    logger.info("Saved scene %d (%s) -> %s", scene.number, scene.title, output_path)
    return output_path


def _download_gcs(uri: str, dest: Path) -> None:
    """Download a file from Google Cloud Storage.

    Args:
        uri: GCS URI (gs://bucket/path)
        dest: Local destination path

    Raises:
        RuntimeError: If download fails.
    """
    import subprocess

    result = subprocess.run(
        ["gsutil", "cp", uri, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gsutil download failed: {result.stderr}")
