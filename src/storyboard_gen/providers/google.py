# ABOUTME: Google Vertex AI / Gemini provider for storyboard-gen.
# ABOUTME: Generates stills via Imagen and clips via Veo through the GenAI SDK.

import logging
import subprocess
import time
from pathlib import Path

from storyboard_gen.providers.base import ImageProvider

logger = logging.getLogger(__name__)

DEFAULT_IMAGEN_MODEL = "imagen-4.0-generate-001"
IMAGEN_CAPABILITY_MODEL = "imagen-3.0-capability-001"
DEFAULT_VEO_MODEL = "veo-3.1-fast-generate-001"
MAX_IMAGEN_REFS = 4
MAX_VEO_REFS = 3


class GoogleProvider(ImageProvider):
    """Google Vertex AI / Gemini image and video provider."""

    def __init__(self, model: str, options: dict | None = None):
        self.model = model
        self.options = options or {}
        self._client = None
        self._gcs_bucket = None

    def _get_client(self):
        """Lazily create the Google GenAI client."""
        if self._client is None:
            from google.genai import Client

            from storyboard_gen.config import get_env_config

            config = get_env_config()
            self._gcs_bucket = config.get("gcs_bucket")
            if config["use_vertex"]:
                if not config["project"]:
                    raise ValueError(
                        "GOOGLE_CLOUD_PROJECT must be set when USE_VERTEX=true"
                    )
                if not config["location"]:
                    raise ValueError(
                        "GOOGLE_CLOUD_LOCATION must be set when USE_VERTEX=true"
                    )
                self._client = Client(
                    vertexai=True,
                    project=config["project"],
                    location=config["location"],
                )
            elif config["api_key"]:
                self._client = Client(api_key=config["api_key"])
            else:
                raise ValueError(
                    "No API credentials found. Set GEMINI_API_KEY or USE_VERTEX=true "
                    "with GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION."
                )
        return self._client

    def generate_still(
        self,
        prompt: str,
        output_path: Path,
        aspect_ratio: str,
        reference_images: list[Path] | None = None,
        options: dict | None = None,
        *,
        client: object | None = None,
    ) -> bytes:
        """Generate a still image via Imagen.

        When a single reference image is provided, uses edit_image with
        SubjectReferenceImage on imagen-3.0-capability-001. Otherwise
        uses generate_images on the configured Imagen model.
        """
        from google.genai import types

        if client is None:
            client = self._get_client()

        ref_images = []
        if reference_images:
            for idx, ref_path in enumerate(reference_images, start=1):
                if ref_path.exists():
                    ref_images.append(
                        types.SubjectReferenceImage(
                            reference_id=idx,
                            reference_image=types.Image.from_file(
                                location=str(ref_path)
                            ),
                            config=types.SubjectReferenceConfig(
                                subject_type="SUBJECT_TYPE_PERSON",
                            ),
                        )
                    )
                    logger.info("Reference [%d]: %s", idx, ref_path)
                else:
                    logger.warning("Reference image not found, skipping: %s", ref_path)

        if len(ref_images) > MAX_IMAGEN_REFS:
            logger.warning(
                "Truncating %d reference images to Imagen max of %d",
                len(ref_images),
                MAX_IMAGEN_REFS,
            )
            ref_images = ref_images[:MAX_IMAGEN_REFS]

        if ref_images:
            logger.info(
                "Using edit_image with %d reference(s) on %s",
                len(ref_images),
                IMAGEN_CAPABILITY_MODEL,
            )
            response = client.models.edit_image(
                model=IMAGEN_CAPABILITY_MODEL,
                prompt=prompt,
                reference_images=ref_images,
                config=types.EditImageConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                ),
            )
        else:
            response = client.models.generate_images(
                model=self.model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                ),
            )

        if not response.generated_images:
            model_used = IMAGEN_CAPABILITY_MODEL if ref_images else self.model
            raise RuntimeError(
                f"No image generated. The {model_used} safety filter likely "
                f"rejected the prompt or reference image combination. "
                f"Try revising the prompt."
            )

        return response.generated_images[0].image.image_bytes

    def generate_clip(
        self,
        prompt: str,
        output_path: Path,
        aspect_ratio: str,
        duration: float,
        reference_images: list[Path] | None = None,
        options: dict | None = None,
        *,
        source_frame: Path | None = None,
        last_frame: Path | None = None,
        extend_from_video: Path | None = None,
        seed: int | None = None,
        number_of_videos: int = 1,
        client: object | None = None,
        poll_interval: int = 10,
        max_wait: int = 600,
        project_dir: Path | None = None,
        scene_number: str | None = None,
    ) -> list[bytes]:
        """Generate a video clip via Veo.

        Builds a GenerateVideosConfig with aspect_ratio, reference_images,
        last_frame, seed, and number_of_videos. Optionally passes
        source_frame as image= or extend_from_video as video=.

        When project_dir and scene_number are provided, writes operation
        log entries to logs/operations.jsonl for crash recovery.
        """
        from google.genai import types

        if client is None:
            client = self._get_client()

        # Build reference images list for config.
        # Veo requires VideoGenerationReferenceImage wrappers (not bare Image).
        # reference_images is not supported when image= or video= is set.
        ref_images = []
        if reference_images and source_frame is None and extend_from_video is None:
            for ref_path in reference_images:
                if ref_path.exists():
                    ref_images.append(
                        types.VideoGenerationReferenceImage(
                            image=types.Image.from_file(location=str(ref_path)),
                            reference_type="ASSET",
                        )
                    )
                    logger.info("Clip reference: %s", ref_path)
                else:
                    logger.warning("Reference image not found, skipping: %s", ref_path)
        elif reference_images and (source_frame or extend_from_video):
            logger.info(
                "Skipping reference_images — not supported with %s",
                "source_frame" if source_frame else "extend_from_video",
            )

        if len(ref_images) > MAX_VEO_REFS:
            logger.warning(
                "Truncating %d reference images to Veo max of %d",
                len(ref_images),
                MAX_VEO_REFS,
            )
            ref_images = ref_images[:MAX_VEO_REFS]

        # Build config
        veo_duration = max(5, min(8, int(duration)))
        config = types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            reference_images=ref_images or None,
            number_of_videos=number_of_videos,
            duration_seconds=veo_duration,
        )
        if self._gcs_bucket:
            config.output_gcs_uri = self._gcs_bucket
        if last_frame is not None:
            config.last_frame = types.Image.from_file(location=str(last_frame))
        if seed is not None:
            config.seed = seed

        # Build generate_videos kwargs
        gen_kwargs = {
            "model": self.model,
            "prompt": prompt,
            "config": config,
        }

        if source_frame is not None:
            gen_kwargs["image"] = types.Image.from_file(location=str(source_frame))
            logger.info("Image-to-video source frame: %s", source_frame)

        if extend_from_video is not None:
            video_bytes = extend_from_video.read_bytes()
            gen_kwargs["video"] = types.Video(video_bytes=video_bytes)
            logger.info("Extending from video: %s", extend_from_video)

        operation = client.models.generate_videos(**gen_kwargs)

        op_id = getattr(operation, "name", None) or "unknown"
        if project_dir and scene_number:
            from storyboard_gen.operation_log import log_operation

            log_operation(
                project_dir=project_dir,
                scene_number=scene_number,
                scene_type="clip",
                provider="google",
                model=self.model,
                operation_id=op_id,
                status="submitted",
            )

        elapsed = 0
        while not operation.done:
            if elapsed >= max_wait:
                if project_dir and scene_number:
                    log_operation(
                        project_dir=project_dir,
                        scene_number=scene_number,
                        scene_type="clip",
                        provider="google",
                        model=self.model,
                        operation_id=op_id,
                        status="timed_out",
                    )
                raise RuntimeError(f"Video generation timed out after {max_wait}s")
            logger.info("Waiting for video generation (%ds elapsed)...", elapsed)
            time.sleep(poll_interval)
            elapsed += poll_interval
            operation = client.operations.get(operation)

        if project_dir and scene_number:
            log_operation(
                project_dir=project_dir,
                scene_number=scene_number,
                scene_type="clip",
                provider="google",
                model=self.model,
                operation_id=op_id,
                status="completed",
            )

        # operations.get() populates 'response'; direct return populates 'result'
        video_response = operation.response or operation.result
        if not video_response or not video_response.generated_videos:
            raise RuntimeError("No video generated")

        results = []
        for video_entry in video_response.generated_videos:
            if hasattr(video_entry, "video") and hasattr(
                video_entry.video, "video_bytes"
            ):
                if video_entry.video.video_bytes:
                    results.append(video_entry.video.video_bytes)
                    continue
            if hasattr(video_entry, "video") and hasattr(video_entry.video, "uri"):
                if video_entry.video.uri:
                    logger.info("Downloading from %s", video_entry.video.uri)
                    _download_gcs(video_entry.video.uri, output_path)
                    results.append(output_path.read_bytes())
                    continue
            raise RuntimeError("Unexpected video response format")

        return results


def _download_gcs(uri: str, dest: Path) -> None:
    """Download a file from Google Cloud Storage."""
    result = subprocess.run(
        ["gsutil", "cp", uri, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gsutil download failed: {result.stderr}")
