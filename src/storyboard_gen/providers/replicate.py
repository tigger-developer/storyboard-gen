# ABOUTME: Replicate provider for storyboard-gen.
# ABOUTME: Generates stills via Flux models through the replicate SDK.

import logging
from pathlib import Path

from storyboard_gen.errors import clean_api_error
from storyboard_gen.providers.base import ImageProvider

try:
    import replicate
except ImportError:
    replicate = None  # type: ignore[assignment] — optional SDK; checked at runtime

logger = logging.getLogger(__name__)


class ReplicateProvider(ImageProvider):
    """Replicate image provider using Flux models."""

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
        *,
        scene_characters: list | None = None,
        project_dir: Path | None = None,
        style_reference_images: list[Path] | None = None,
    ) -> bytes:
        """Generate a still image via Replicate Flux models.

        Uses replicate.run() for synchronous generation. The response
        is a FileOutput (single image) or list of FileOutput objects
        depending on the model.

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
            ImportError: If replicate is not installed.
        """
        if replicate is None:
            raise ImportError("replicate is not installed. Run: pip install replicate")

        input_args = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "output_format": "png",
            "safety_tolerance": 6,
        }

        # Merge provider options (seed, safety_tolerance, etc.)
        merged_options = self.options.copy()
        if options:
            merged_options.update(options)
        input_args.update(merged_options)

        # Pass first valid reference image for img2img.
        # Replicate only supports a single reference; warn when truncating.
        # flux-1.1-pro uses "image_prompt"; flux-dev uses "image".
        if reference_images:
            if len(reference_images) > 1:
                logger.warning(
                    "Replicate provider only supports 1 reference image; "
                    "using first of %d provided",
                    len(reference_images),
                )
            ref_key = "image_prompt" if "flux-1.1-pro" in self.model else "image"
            for ref_path in reference_images:
                if ref_path.exists():
                    input_args[ref_key] = open(ref_path, "rb")  # noqa: SIM115 — handle passed to SDK which manages lifecycle
                    logger.info("Reference image: %s", ref_path)
                    break

        logger.info("Generating still via Replicate model=%s", self.model)
        logger.debug("Input: %s", input_args)

        try:
            output = replicate.run(self.model, input=input_args)
        except (
            Exception
        ) as exc:  # Replicate SDK may raise any type; log trace, re-raise clean
            logger.error(
                "Replicate API error for %s: %s", self.model, exc, exc_info=True
            )
            raise RuntimeError(
                f"Replicate API error: {clean_api_error(str(exc))}"
            ) from exc

        if output is None:
            raise RuntimeError(
                f"No image generated. The Replicate {self.model} safety filter "
                f"likely rejected the prompt. Try revising the prompt."
            )

        # Handle both single FileOutput (flux-1.1-pro) and list (flux-dev)
        if isinstance(output, list):
            if not output:
                raise RuntimeError(
                    f"No image generated. The Replicate {self.model} returned "
                    f"an empty result list."
                )
            file_output = output[0]
        else:
            file_output = output

        image_bytes = file_output.read()
        logger.info("Downloaded %d bytes from Replicate", len(image_bytes))
        return image_bytes

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
        scene_characters: list | None = None,
        project_dir: Path | None = None,
        scene_number: str | None = None,
    ) -> list[bytes]:
        """Replicate provider does not support video generation.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            f"Replicate provider ({self.model}) does not support video generation. "
            f"Use Google (Veo) for clips."
        )
