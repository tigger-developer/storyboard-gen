# ABOUTME: FAL.ai provider for storyboard-gen.
# ABOUTME: Generates stills via Flux and Kontext models through the fal-client SDK.

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
    """FAL.ai image provider using Flux and Kontext models."""

    def __init__(self, model: str, options: dict | None = None):
        self.model = model
        self.options = options or {}

    @property
    def _is_kontext(self) -> bool:
        """Detect whether this provider is configured for a Kontext model."""
        return "kontext" in self.model.lower()

    def _upload_reference(self, reference_images: list[Path] | None) -> str | None:
        """Upload a single reference image to FAL CDN if it exists.

        Args:
            reference_images: Optional list of reference image paths.

        Returns:
            CDN URL string, or None if no valid reference.
        """
        if reference_images and len(reference_images) == 1:
            ref_path = reference_images[0]
            if ref_path.exists():
                ref_url = fal_client.upload_file(str(ref_path))
                logger.info("Uploaded reference -> %s", ref_url)
                return ref_url
        return None

    def _build_kontext_args(
        self, prompt: str, aspect_ratio: str, ref_url: str | None
    ) -> tuple[str, dict]:
        """Build arguments and endpoint for Kontext models.

        Kontext has two modes:
        - Image-to-image (base endpoint): requires image_url, uses raw aspect_ratio.
        - Text-to-image (/text-to-image suffix): uses image_size presets.

        Args:
            prompt: Full prompt text.
            aspect_ratio: Raw "W:H" string.
            ref_url: Uploaded reference URL, or None.

        Returns:
            Tuple of (endpoint, arguments dict).
        """
        if ref_url:
            # Image-to-image: base endpoint, image_url, raw aspect_ratio
            endpoint = self.model
            arguments = {
                "prompt": prompt,
                "image_url": ref_url,
                "aspect_ratio": aspect_ratio,
                "num_images": 1,
                "output_format": "png",
            }
        else:
            # Text-to-image: append /text-to-image, use image_size preset
            endpoint = self.model.rstrip("/") + "/text-to-image"
            image_size = _map_aspect_ratio(aspect_ratio)
            arguments = {
                "prompt": prompt,
                "image_size": image_size,
                "num_images": 1,
                "output_format": "png",
            }
        return endpoint, arguments

    def _build_flux_args(
        self, prompt: str, aspect_ratio: str, ref_url: str | None
    ) -> tuple[str, dict]:
        """Build arguments and endpoint for Flux models.

        Args:
            prompt: Full prompt text.
            aspect_ratio: Raw "W:H" string.
            ref_url: Uploaded reference URL, or None.

        Returns:
            Tuple of (endpoint, arguments dict).
        """
        image_size = _map_aspect_ratio(aspect_ratio)
        arguments = {
            "prompt": prompt,
            "image_size": image_size,
            "num_images": 1,
            "output_format": "png",
        }
        if ref_url:
            arguments["reference_image_url"] = ref_url
        return self.model, arguments

    def generate_still(
        self,
        prompt: str,
        output_path: Path,
        aspect_ratio: str,
        reference_images: list[Path] | None = None,
        options: dict | None = None,
    ) -> bytes:
        """Generate a still image via FAL Flux or Kontext models.

        Uses fal_client.subscribe() for synchronous generation.
        Kontext models route to image-to-image (with reference) or
        text-to-image (without). Flux models use reference_image_url.

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

        ref_url = self._upload_reference(reference_images)

        if self._is_kontext:
            endpoint, arguments = self._build_kontext_args(
                prompt, aspect_ratio, ref_url
            )
        else:
            endpoint, arguments = self._build_flux_args(prompt, aspect_ratio, ref_url)

        # Merge provider options (seed, safety_tolerance, etc.)
        merged_options = self.options.copy()
        if options:
            merged_options.update(options)
        arguments.update(merged_options)

        logger.info(
            "Generating still via FAL model=%s endpoint=%s", self.model, endpoint
        )
        logger.debug("Arguments: %s", arguments)

        try:
            result = fal_client.subscribe(endpoint, arguments=arguments)
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
        duration: float,
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
