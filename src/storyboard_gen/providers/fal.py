# ABOUTME: FAL.ai provider for storyboard-gen.
# ABOUTME: Generates stills via Flux/Kontext and clips via Kling through the fal-client SDK.

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
        """Upload the first valid reference image to FAL CDN.

        FAL models only support a single reference image. When multiple
        are provided, the first existing file is used and a warning is logged.

        Args:
            reference_images: Optional list of reference image paths.

        Returns:
            CDN URL string, or None if no valid reference.
        """
        if not reference_images:
            return None
        if len(reference_images) > 1:
            logger.warning(
                "FAL provider only supports 1 reference image; "
                "using first of %d provided",
                len(reference_images),
            )
        for ref_path in reference_images:
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

    @property
    def _is_video_model(self) -> bool:
        """Detect whether this provider is configured for a video model."""
        return "kling-video" in self.model.lower()

    @property
    def _is_v3(self) -> bool:
        """Detect whether this is a Kling v3+ model (different param names)."""
        return "/v3/" in self.model.lower()

    def _build_video_args(
        self,
        prompt: str,
        aspect_ratio: str,
        duration: float,
        source_frame_url: str | None,
        last_frame_url: str | None,
    ) -> dict:
        """Build arguments for Kling video generation.

        Args:
            prompt: Full prompt text.
            aspect_ratio: Raw "W:H" string.
            duration: Duration in seconds.
            source_frame_url: Uploaded source frame URL, or None.
            last_frame_url: Uploaded last frame URL, or None.

        Returns:
            Arguments dict for fal_client.subscribe().
        """
        arguments: dict = {
            "prompt": prompt,
            "duration": str(int(duration)),
            "aspect_ratio": aspect_ratio,
            "generate_audio": False,
        }

        if source_frame_url:
            if self._is_v3:
                arguments["start_image_url"] = source_frame_url
            else:
                arguments["image_url"] = source_frame_url

        if last_frame_url:
            if self._is_v3:
                arguments["end_image_url"] = last_frame_url
            else:
                arguments["tail_image_url"] = last_frame_url

        return arguments

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
    ) -> list[bytes]:
        """Generate a video clip via FAL Kling models.

        Uses fal_client.subscribe() for synchronous generation.
        Supports image-to-video via source_frame and last_frame.

        Raises:
            NotImplementedError: If model is not a video model (e.g. Flux/Kontext).
            RuntimeError: On generation failure.
            ImportError: If fal-client is not installed.
        """
        if not self._is_video_model:
            raise NotImplementedError(
                f"FAL provider ({self.model}) does not support video generation. "
                f"Use a Kling model or Google (Veo) for clips."
            )

        if fal_client is None:
            raise ImportError(
                "fal-client is not installed. Run: pip install fal-client"
            )

        # Upload source_frame and last_frame to CDN
        source_frame_url = None
        if source_frame is not None and source_frame.exists():
            source_frame_url = fal_client.upload_file(str(source_frame))
            logger.info("Uploaded source frame -> %s", source_frame_url)

        last_frame_url = None
        if last_frame is not None and last_frame.exists():
            last_frame_url = fal_client.upload_file(str(last_frame))
            logger.info("Uploaded last frame -> %s", last_frame_url)

        arguments = self._build_video_args(
            prompt, aspect_ratio, duration, source_frame_url, last_frame_url
        )

        # Merge provider options (cfg_scale, negative_prompt, etc.)
        merged_options = self.options.copy()
        if options:
            merged_options.update(options)
        arguments.update(merged_options)

        # Auto-route endpoint based on whether source_frame is set (#36)
        endpoint = self.model
        has_source = source_frame_url is not None
        if has_source and "text-to-video" in endpoint:
            endpoint = endpoint.replace("text-to-video", "image-to-video")
            logger.info("Auto-routed endpoint to image-to-video (source_frame set)")
        elif not has_source and "image-to-video" in endpoint:
            endpoint = endpoint.replace("image-to-video", "text-to-video")
            logger.info("Auto-routed endpoint to text-to-video (no source_frame)")

        logger.info(
            "Generating clip via FAL model=%s endpoint=%s", self.model, endpoint
        )
        logger.debug("Arguments: %s", arguments)

        try:
            result = fal_client.subscribe(endpoint, arguments=arguments)
        except Exception as exc:
            raise RuntimeError(f"FAL API error: {exc}") from exc

        video = result.get("video")
        if not video or not video.get("url"):
            raise RuntimeError(
                f"No video generated. The FAL {self.model} safety filter likely "
                f"rejected the prompt or source image. Try revising them."
            )

        video_url = video["url"]
        logger.info("Downloading generated video from %s", video_url)
        return [_download_url(video_url)]
