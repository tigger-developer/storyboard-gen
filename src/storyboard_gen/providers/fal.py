# ABOUTME: FAL.ai provider for storyboard-gen.
# ABOUTME: Generates stills via Flux models through the fal-client SDK.

import logging
import urllib.request
from pathlib import Path

from storyboard_gen.providers.base import ImageProvider

try:
    import fal_client
except ImportError:
    fal_client = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

ASPECT_RATIO_MAP = {
    "9:16": "portrait_16_9",
    "16:9": "landscape_16_9",
    "4:3": "landscape_4_3",
    "1:1": "square_hd",
}


def _map_aspect_ratio(aspect_ratio: str) -> str:
    """Map a W:H aspect ratio string to a FAL image_size preset.

    Args:
        aspect_ratio: Ratio as "W:H" string (e.g. "9:16").

    Returns:
        FAL image_size preset string.

    Raises:
        ValueError: If the aspect ratio has no FAL equivalent.
    """
    preset = ASPECT_RATIO_MAP.get(aspect_ratio)
    if preset is None:
        raise ValueError(
            f"Unsupported aspect ratio '{aspect_ratio}' for FAL. "
            f"Must be one of: {', '.join(sorted(ASPECT_RATIO_MAP))}"
        )
    return preset


def _download_url(url: str) -> bytes:
    """Download bytes from a URL."""
    with urllib.request.urlopen(url) as resp:  # noqa: S310 — URL from trusted FAL API
        return resp.read()


class FalProvider(ImageProvider):
    """FAL.ai image provider using Flux models."""

    def __init__(self, model: str, options: dict | None = None):
        self.model = model
        self.options = options or {}

    def generate_still(
        self,
        prompt: str,
        output_path: Path,
        aspect_ratio: str,
        reference_images: list[Path] | None = None,
        options: dict | None = None,
    ) -> bytes:
        """Generate a still image via FAL Flux models.

        Uses fal_client.subscribe() for synchronous generation.
        When a single reference image is provided, uploads it to FAL CDN
        and passes it as reference_image_url for style guidance.

        Args:
            prompt: Full prompt (style_prefix + scene prompt).
            output_path: Where to save the output PNG.
            aspect_ratio: Target ratio as "W:H" string (e.g. "9:16").
            reference_images: Optional list of reference image paths.
            options: Provider-specific options from project.yaml.

        Returns:
            Raw image bytes (PNG).

        Raises:
            RuntimeError: On generation failure.
            ImportError: If fal-client is not installed.
        """
        if fal_client is None:
            raise ImportError(
                "fal-client is not installed. Run: pip install fal-client"
            )

        image_size = _map_aspect_ratio(aspect_ratio)

        arguments = {
            "prompt": prompt,
            "image_size": image_size,
            "num_images": 1,
            "output_format": "png",
        }

        # Merge provider options (seed, safety_tolerance, etc.)
        merged_options = self.options.copy()
        if options:
            merged_options.update(options)
        arguments.update(merged_options)

        # Upload single reference image for style guidance
        if reference_images and len(reference_images) == 1:
            ref_path = reference_images[0]
            if ref_path.exists():
                ref_url = fal_client.upload_file(str(ref_path))
                arguments["reference_image_url"] = ref_url
                logger.info("Uploaded reference -> %s", ref_url)

        logger.info("Generating still via FAL model=%s", self.model)
        logger.debug("Arguments: %s", arguments)

        try:
            result = fal_client.subscribe(self.model, arguments=arguments)
        except Exception as exc:
            raise RuntimeError(f"FAL API error: {exc}") from exc

        images = result.get("images", [])
        if not images:
            raise RuntimeError(
                f"No image generated. The FAL {self.model} safety filter likely "
                f"rejected the prompt. Try revising the prompt."
            )

        image_url = images[0]["url"]
        logger.info("Downloading generated image from %s", image_url)
        return _download_url(image_url)

    def generate_clip(
        self,
        prompt: str,
        output_path: Path,
        aspect_ratio: str,
        duration: int,
        reference_images: list[Path] | None = None,
        options: dict | None = None,
    ) -> bytes:
        """FAL provider does not support video generation.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            f"FAL provider ({self.model}) does not support video generation. "
            f"Use Google (Veo) for clips."
        )
