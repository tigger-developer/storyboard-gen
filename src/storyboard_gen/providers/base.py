# ABOUTME: Abstract base class for image/video generation providers.
# ABOUTME: Defines the interface that Google, FAL, and Replicate providers implement.

from abc import ABC, abstractmethod
from pathlib import Path


class ImageProvider(ABC):
    """Abstract base for image and video generation providers."""

    @abstractmethod
    def generate_still(
        self,
        prompt: str,
        output_path: Path,
        aspect_ratio: str,
        reference_images: list[Path] | None = None,
        options: dict | None = None,
    ) -> bytes:
        """Generate a still image from a prompt.

        Args:
            prompt: Full prompt (style_prefix + scene prompt).
            output_path: Where to save the output PNG.
            aspect_ratio: Target ratio as "W:H" string (e.g. "9:16").
            reference_images: Optional list of reference image paths.
            options: Provider-specific options from project.yaml.

        Returns:
            Raw image bytes (PNG).

        Raises:
            RuntimeError: On generation failure. NEVER silently degrade.
        """

    @abstractmethod
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
        """Generate a video clip from a prompt.

        Args:
            prompt: Full prompt (style_prefix + scene prompt).
            output_path: Where to save the output MP4.
            aspect_ratio: Target ratio as "W:H" string (e.g. "9:16").
            duration: Target duration in seconds.
            reference_images: Optional list of reference image paths.
            options: Provider-specific options from project.yaml.
            source_frame: Image to use as first frame (image-to-video).
            last_frame: Image to interpolate to (requires source_frame).
            extend_from_video: Path to video to extend from.
            seed: Reproducibility seed.
            number_of_videos: Number of variant takes to generate (1-4).

        Returns:
            List of raw video bytes (MP4), one per variant.

        Raises:
            RuntimeError: On generation failure.
            NotImplementedError: If provider doesn't support video.
        """
