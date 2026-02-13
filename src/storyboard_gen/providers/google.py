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


class GoogleProvider(ImageProvider):
    """Google Vertex AI / Gemini image and video provider."""

    def __init__(self, model: str, options: dict | None = None):
        self.model = model
        self.options = options or {}
        self._client = None

    def _get_client(self):
        """Lazily create the Google GenAI client."""
        if self._client is None:
            from google.genai import Client

            from storyboard_gen.config import get_env_config

            config = get_env_config()
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

        # Only use subject references for single reference images to avoid
        # reference bleeding across characters.
        ref_images = []
        if reference_images and len(reference_images) == 1:
            ref_path = reference_images[0]
            if ref_path.exists():
                ref_images.append(
                    types.SubjectReferenceImage(
                        reference_id=1,
                        reference_image=types.Image.from_file(location=str(ref_path)),
                        config=types.SubjectReferenceConfig(
                            subject_type="SUBJECT_TYPE_PERSON",
                        ),
                    )
                )
                logger.info("Reference [1]: %s", ref_path)

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
        client: object | None = None,
        poll_interval: int = 10,
        max_wait: int = 600,
    ) -> bytes:
        """Generate a video clip via Veo."""
        if client is None:
            client = self._get_client()

        operation = client.models.generate_videos(
            model=self.model,
            prompt=prompt,
        )

        elapsed = 0
        while not operation.done:
            if elapsed >= max_wait:
                raise RuntimeError(f"Video generation timed out after {max_wait}s")
            logger.info("Waiting for video generation (%ds elapsed)...", elapsed)
            time.sleep(poll_interval)
            elapsed += poll_interval

        if not operation.result or not operation.result.generated_videos:
            raise RuntimeError("No video generated")

        video = operation.result.generated_videos[0]

        if hasattr(video, "video") and hasattr(video.video, "video_bytes"):
            return video.video.video_bytes
        if hasattr(video, "video") and hasattr(video.video, "uri"):
            logger.info("Downloading from %s", video.video.uri)
            _download_gcs(video.video.uri, output_path)
            return output_path.read_bytes()

        raise RuntimeError("Unexpected video response format")


def _download_gcs(uri: str, dest: Path) -> None:
    """Download a file from Google Cloud Storage."""
    result = subprocess.run(
        ["gsutil", "cp", uri, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gsutil download failed: {result.stderr}")
