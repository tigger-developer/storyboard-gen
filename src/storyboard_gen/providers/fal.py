# ABOUTME: FAL.ai provider for storyboard-gen.
# ABOUTME: Generates stills and clips via fal-client SDK for multiple model families.

import logging
import re
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

from storyboard_gen.errors import clean_api_error
from storyboard_gen.providers.base import ImageProvider

try:
    import fal_client
except ImportError:
    fal_client = None  # type: ignore[assignment] — optional SDK; checked at runtime

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


class StillHandler(ABC):
    """Base class for model-family-specific still argument building.

    Each handler encapsulates the argument construction, reference upload,
    prompt rewriting, and safety defaults for a particular FAL model family.
    """

    @abstractmethod
    def match(self, model: str) -> bool:
        """Return True if this handler handles the given model ID."""

    @abstractmethod
    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        """Build (endpoint, arguments) for still generation."""

    @abstractmethod
    def safety_defaults(self) -> dict:
        """Return safety default key-value pairs for this model family."""


class IdeogramCharacterHandler(StillHandler):
    """Handler for Ideogram Character models (dual-channel refs)."""

    def match(self, model: str) -> bool:
        lower = model.lower()
        return "ideogram" in lower and "character" in lower

    def safety_defaults(self) -> dict:
        return {}

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        endpoint, arguments = provider._build_ideogram_character_args(
            prompt, aspect_ratio, scene_characters, style_reference_images
        )
        return endpoint, arguments


class O1ImageHandler(StillHandler):
    """Handler for Kling O1 Image models (multi-ref @ImageN mapping)."""

    def match(self, model: str) -> bool:
        lower = model.lower()
        return "kling-image" in lower and "/o1" in lower

    def safety_defaults(self) -> dict:
        return {}

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        if scene_characters:
            prompt = provider._rewrite_prompt(prompt, scene_characters)
            endpoint, arguments = provider._build_o1_image_args(
                prompt, aspect_ratio, scene_characters
            )
        else:
            endpoint = provider.model
            arguments = {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "num_images": 1,
                "output_format": "png",
            }
        return endpoint, arguments


class KontextMultiHandler(StillHandler):
    """Handler for Kontext Max Multi models (multi-ref, implicit mapping)."""

    def match(self, model: str) -> bool:
        lower = model.lower()
        return "kontext" in lower and "multi" in lower

    def safety_defaults(self) -> dict:
        return {"safety_tolerance": "6"}

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        if scene_characters:
            prompt = provider._rewrite_prompt(prompt, scene_characters)
            endpoint, arguments = provider._build_kontext_multi_args(
                prompt, aspect_ratio, scene_characters
            )
        else:
            endpoint = provider.model
            arguments = {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "num_images": 1,
                "output_format": "png",
            }
        return endpoint, arguments


class KontextHandler(StillHandler):
    """Handler for Kontext Pro models (i2i/t2i routing)."""

    def match(self, model: str) -> bool:
        return "kontext" in model.lower()

    def safety_defaults(self) -> dict:
        return {"safety_tolerance": "6"}

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        ref_url = provider._upload_reference(reference_images)
        return provider._build_kontext_args(prompt, aspect_ratio, ref_url)


class Flux2ProHandler(StillHandler):
    """Handler for Flux 2 Pro/Max models (multi-ref via image_urls + @imageN prompt)."""

    def match(self, model: str) -> bool:
        lower = model.lower()
        return "flux-2-pro" in lower or "flux-2-max" in lower

    def safety_defaults(self) -> dict:
        return {"enable_safety_checker": False}

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        # Strip /edit suffix to get clean base model
        base_model = re.sub(r"/edit$", "", provider.model, flags=re.IGNORECASE)

        if scene_characters:
            # Upload all character refs
            all_refs: list[Path] = []
            for char in scene_characters:
                all_refs.extend(r for r in char.reference if r.exists())
            image_urls = provider._upload_all_references(all_refs)

            # Rewrite @character_id → @imageN (lowercase per Flux 2 Pro API)
            prompt = provider._rewrite_prompt(
                prompt, scene_characters, tag_prefix="image"
            )

            endpoint = base_model.rstrip("/") + "/edit"
            image_size = _map_aspect_ratio(aspect_ratio)
            arguments: dict = {
                "prompt": prompt,
                "image_size": image_size,
                "image_urls": image_urls,
                "num_images": 1,
                "output_format": "png",
            }
        else:
            endpoint = base_model
            image_size = _map_aspect_ratio(aspect_ratio)
            arguments = {
                "prompt": prompt,
                "image_size": image_size,
                "num_images": 1,
                "output_format": "png",
            }
        return endpoint, arguments


class InstantCharacterHandler(StillHandler):
    """Handler for Instant Character models (single ref via image_url)."""

    def match(self, model: str) -> bool:
        return "instant-character" in model.lower()

    def safety_defaults(self) -> dict:
        return {"enable_safety_checker": False}

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        image_size = _map_aspect_ratio(aspect_ratio)
        arguments: dict = {
            "prompt": prompt,
            "image_size": image_size,
            "num_images": 1,
            "output_format": "png",
        }
        ref_url = provider._upload_reference(reference_images)
        if ref_url:
            arguments["image_url"] = ref_url
        return provider.model, arguments


class IdeogramV3Handler(StillHandler):
    """Handler for Ideogram V3 models (typography, style refs only)."""

    def match(self, model: str) -> bool:
        lower = model.lower()
        return "ideogram" in lower and "/v3" in lower

    def safety_defaults(self) -> dict:
        return {}

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        image_size = _map_aspect_ratio(aspect_ratio)
        arguments: dict = {
            "prompt": prompt,
            "image_size": image_size,
            "num_images": 1,
            "output_format": "png",
            "style": "AUTO",
        }
        # Style refs → image_urls (same channel as ideogram/character)
        if style_reference_images:
            existing_style = [r for r in style_reference_images if r.exists()]
            if existing_style:
                style_urls = provider._upload_all_references(existing_style)
                arguments["image_urls"] = style_urls
        return provider.model, arguments


class EditHandler(StillHandler):
    """Configurable handler for models using image_urls + /edit endpoint pattern.

    Replaces per-model-family handler classes with declarative configuration:
    - patterns: model ID substrings to match
    - sizing: "image_size" (preset mapping) or "aspect_ratio" (raw passthrough)
    - safety: default safety options dict
    - supports_edit: whether the model supports /edit endpoint with image_urls

    Checks both scene_characters and reference_images for refs (#106).
    """

    def __init__(
        self,
        patterns: list[str],
        sizing: str = "image_size",
        safety: dict | None = None,
        supports_edit: bool = True,
        edit_suffix: str | None = "/edit",
        ref_field: str = "image_urls",
        edit_accepts_sizing: bool = True,
    ):
        self._patterns = patterns
        self._sizing = sizing
        self._safety = safety or {}
        self._supports_edit = supports_edit
        self._edit_suffix = edit_suffix
        self._ref_field = ref_field
        self._edit_accepts_sizing = edit_accepts_sizing

    def match(self, model: str) -> bool:
        lower = model.lower()
        return any(p in lower for p in self._patterns)

    def safety_defaults(self) -> dict:
        return self._safety

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        # Normalize base model: strip edit suffix and /text-to-image
        base_model = provider.model
        for suffix in [self._edit_suffix, "/text-to-image"]:
            if suffix and base_model.lower().endswith(suffix.lower()):
                base_model = base_model[: -len(suffix)]
                break

        # Collect refs from characters or scene-level references (#106)
        image_urls = None
        if self._supports_edit:
            if scene_characters:
                all_refs = [
                    r for c in scene_characters for r in c.reference if r.exists()
                ]
                image_urls = provider._upload_all_references(all_refs)
            elif reference_images:
                image_urls = provider._upload_all_references(
                    [r for r in reference_images if r.exists()]
                )

        if image_urls:
            if self._edit_suffix:
                endpoint = base_model.rstrip("/") + self._edit_suffix
            else:
                endpoint = provider.model
            # Use ref_field: singular (string) or plural (list)
            if self._ref_field == "image_url":
                ref_value = image_urls[0]
            else:
                ref_value = image_urls
            arguments: dict = {
                "prompt": prompt,
                self._ref_field: ref_value,
                "num_images": 1,
                "output_format": "png",
            }
            # Some edit endpoints don't accept sizing parameters
            if self._edit_accepts_sizing:
                if self._sizing == "aspect_ratio":
                    arguments["aspect_ratio"] = aspect_ratio
                else:
                    arguments["image_size"] = _map_aspect_ratio(aspect_ratio)
        else:
            endpoint = base_model
            arguments = {
                "prompt": prompt,
                "num_images": 1,
                "output_format": "png",
            }
            # Base endpoint always accepts sizing
            if self._sizing == "aspect_ratio":
                arguments["aspect_ratio"] = aspect_ratio
            else:
                arguments["image_size"] = _map_aspect_ratio(aspect_ratio)

        return endpoint, arguments


class Flux2Handler(StillHandler):
    """Handler for Flux 2 models (no reference support)."""

    def match(self, model: str) -> bool:
        return "flux-2" in model.lower()

    def safety_defaults(self) -> dict:
        return {"enable_safety_checker": False}

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        ref_url = provider._upload_reference(reference_images)
        return provider._build_flux_args(prompt, aspect_ratio, ref_url)


class FluxHandler(StillHandler):
    """Handler for Flux 1.x models (single reference via reference_image_url). Fallback handler."""

    def match(self, model: str) -> bool:
        return True

    def safety_defaults(self) -> dict:
        return {"enable_safety_checker": False}

    def build_args(
        self,
        provider: "FalProvider",
        prompt: str,
        aspect_ratio: str,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
        project_dir: Path | None,
    ) -> tuple[str, dict]:
        ref_url = provider._upload_reference(reference_images)
        return provider._build_flux_args(prompt, aspect_ratio, ref_url)


# Registry: order matters — more specific handlers first, FluxHandler (fallback) last.
_STILL_HANDLERS: list[StillHandler] = [
    IdeogramCharacterHandler(),
    IdeogramV3Handler(),
    O1ImageHandler(),
    KontextMultiHandler(),
    KontextHandler(),
    EditHandler(
        ["grok-imagine-image"], sizing="aspect_ratio", edit_accepts_sizing=False
    ),
    EditHandler(["seedream"], safety={"enable_safety_checker": False}),
    EditHandler(
        ["hunyuan-image"], safety={"enable_safety_checker": False}, supports_edit=False
    ),
    EditHandler(
        ["recraft"], safety={"enable_safety_checker": False}, supports_edit=False
    ),
    EditHandler(["firered"], edit_suffix=None),
    EditHandler(["qwen-image-edit"], edit_suffix=None),
    EditHandler(["qwen-image"], supports_edit=False),
    EditHandler(["glm-image"], edit_suffix="/image-to-image"),
    EditHandler(
        ["emu-3.5"],
        sizing="aspect_ratio",
        edit_suffix="/edit-image",
        ref_field="image_url",
    ),
    EditHandler(["gpt-image"]),
    EditHandler(["nano-banana"], sizing="aspect_ratio"),
    EditHandler(["reve/fast/remix"], sizing="aspect_ratio", edit_suffix=None),
    EditHandler(
        ["reve"],
        sizing="aspect_ratio",
        ref_field="image_url",
        edit_accepts_sizing=False,
    ),
    InstantCharacterHandler(),
    Flux2ProHandler(),
    EditHandler(["flux-2"], safety={"enable_safety_checker": False}),
    FluxHandler(),
]


def _resolve_still_handler(model: str) -> StillHandler:
    """Resolve the appropriate handler for a given model ID.

    Args:
        model: FAL model ID string.

    Returns:
        The first matching StillHandler instance.
    """
    for handler in _STILL_HANDLERS:
        if handler.match(model):
            return handler
    return _STILL_HANDLERS[-1]


class FalProvider(ImageProvider):
    """FAL.ai image provider using Flux and Kontext models."""

    def __init__(self, model: str, options: dict | None = None):
        self.model = model
        self.options = options or {}

    @property
    def _is_kontext(self) -> bool:
        """Detect whether this provider is configured for a Kontext model."""
        return "kontext" in self.model.lower()

    @property
    def _is_flux2(self) -> bool:
        """Detect whether this provider is configured for a Flux 2 model."""
        return "flux-2" in self.model.lower()

    @property
    def _is_o1_image(self) -> bool:
        """Detect whether this provider is configured for a Kling O1 Image model."""
        lower = self.model.lower()
        return "kling-image" in lower and "/o1" in lower

    @property
    def _is_kontext_multi(self) -> bool:
        """Detect whether this provider is configured for Kontext Max Multi."""
        lower = self.model.lower()
        return "kontext" in lower and "multi" in lower

    @property
    def _is_ideogram_character(self) -> bool:
        """Detect whether this provider is configured for an Ideogram Character model."""
        lower = self.model.lower()
        return "ideogram" in lower and "character" in lower

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
            # Image-to-image: base endpoint, image_url
            endpoint = self.model
            arguments = {
                "prompt": prompt,
                "image_url": ref_url,
                "num_images": 1,
                "output_format": "png",
            }
            # flux-kontext/dev doesn't accept aspect_ratio; kontext pro does
            if "flux-kontext" not in self.model.lower():
                arguments["aspect_ratio"] = aspect_ratio
        elif "flux-kontext" in self.model.lower():
            # Kontext Dev (fal-ai/flux-kontext/dev) is i2i only
            raise ValueError(
                f"{self.model} requires a reference image "
                "(image-to-image only, no text-to-image mode)"
            )
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
            if "flux-general" in self.model.lower():
                arguments["reference_image_url"] = ref_url
            else:
                logger.warning(
                    "Model %s does not support reference_image_url; "
                    "reference will be ignored",
                    self.model,
                )
        return self.model, arguments

    def _build_o1_image_args(
        self,
        prompt: str,
        aspect_ratio: str,
        scene_characters: list,
    ) -> tuple[str, dict]:
        """Build arguments for Kling O1 Image models.

        O1 Image supports multi-reference stills via image_urls and elements.

        Args:
            prompt: Full prompt text (with @character_id tokens).
            aspect_ratio: Raw "W:H" string.
            scene_characters: Ordered list of Character objects.

        Returns:
            Tuple of (endpoint, arguments dict).
        """
        # Collect all reference images from all characters
        all_refs: list[Path] = []
        for char in scene_characters:
            all_refs.extend(r for r in char.reference if r.exists())

        image_urls = self._upload_all_references(all_refs)

        arguments: dict = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "num_images": 1,
            "output_format": "png",
        }
        if image_urls:
            arguments["image_urls"] = image_urls

        return self.model, arguments

    def _build_kontext_multi_args(
        self,
        prompt: str,
        aspect_ratio: str,
        scene_characters: list,
    ) -> tuple[str, dict]:
        """Build arguments for Kontext Max Multi models.

        Kontext Multi accepts multiple reference images via image_urls.
        The model infers associations from prompt context — no explicit
        @ImageN mapping needed.

        Args:
            prompt: Full prompt text.
            aspect_ratio: Raw "W:H" string.
            scene_characters: Ordered list of Character objects.

        Returns:
            Tuple of (endpoint, arguments dict).
        """
        # Collect all reference images from all characters
        all_refs: list[Path] = []
        for char in scene_characters:
            all_refs.extend(r for r in char.reference if r.exists())

        image_urls = self._upload_all_references(all_refs)

        arguments: dict = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "num_images": 1,
            "output_format": "png",
        }
        if image_urls:
            arguments["image_urls"] = image_urls

        return self.model, arguments

    def _build_ideogram_character_args(
        self,
        prompt: str,
        aspect_ratio: str,
        scene_characters: list | None,
        style_reference_images: list[Path] | None,
    ) -> tuple[str, dict]:
        """Build arguments for Ideogram Character models.

        Ideogram Character has two separate reference channels:
        - reference_image_urls: character identity (from scene_characters)
        - image_urls: style/aesthetic reference (from style_reference_images)

        Args:
            prompt: Full prompt text.
            aspect_ratio: Raw "W:H" string.
            scene_characters: Ordered list of Character objects.
            style_reference_images: List of style reference image paths.

        Returns:
            Tuple of (endpoint, arguments dict).
        """
        image_size = _map_aspect_ratio(aspect_ratio)
        arguments: dict = {
            "prompt": prompt,
            "image_size": image_size,
            "num_images": 1,
            "output_format": "png",
            "style": "AUTO",
        }

        # Character refs → reference_image_urls
        if scene_characters:
            char_refs: list[Path] = []
            for char in scene_characters:
                char_refs.extend(r for r in char.reference if r.exists())
            if char_refs:
                char_urls = self._upload_all_references(char_refs)
                arguments["reference_image_urls"] = char_urls

        # Style refs → image_urls (all existing)
        if style_reference_images:
            existing_style = [r for r in style_reference_images if r.exists()]
            if existing_style:
                style_urls = self._upload_all_references(existing_style)
                arguments["image_urls"] = style_urls

        return self.model, arguments

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

        handler = _resolve_still_handler(self.model)
        endpoint, arguments = handler.build_args(
            self,
            prompt,
            aspect_ratio,
            reference_images,
            scene_characters,
            style_reference_images,
            project_dir,
        )

        # Inject safety defaults (overridable by user options)
        arguments.update(handler.safety_defaults())

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
        except (
            Exception
        ) as exc:  # FAL SDK may raise any type; log trace, re-raise clean
            logger.error(
                "FAL still API error for %s: %s", self.model, exc, exc_info=True
            )
            raise RuntimeError(f"FAL API error: {clean_api_error(str(exc))}") from exc

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
        lower = self.model.lower()
        return (
            "kling-video" in lower
            or "/wan" in lower
            or lower.startswith("wan/")
            or "minimax" in lower
            or "grok-imagine-video" in lower
            or "seedance" in lower
            or "hunyuan-video" in lower
        )

    @property
    def _is_wan(self) -> bool:
        """Detect whether this is a Wan video model."""
        lower = self.model.lower()
        return "/wan" in lower or lower.startswith("wan/")

    @property
    def _is_minimax(self) -> bool:
        """Detect whether this is a MiniMax video model."""
        return "minimax" in self.model.lower()

    @property
    def _is_grok_video(self) -> bool:
        """Detect whether this is a Grok Imagine Video model."""
        return "grok-imagine-video" in self.model.lower()

    @property
    def _is_seedance(self) -> bool:
        """Detect whether this is a Seedance video model."""
        return "seedance" in self.model.lower()

    @property
    def _is_hunyuan_video(self) -> bool:
        """Detect whether this is a Hunyuan Video model."""
        return "hunyuan-video" in self.model.lower()

    @property
    def _is_v3(self) -> bool:
        """Detect whether this is a Kling v3+ model (different param names)."""
        return "/v3/" in self.model.lower()

    @property
    def _is_o3(self) -> bool:
        """Detect whether this is a Kling O3 model (supports character elements)."""
        return "/o3/" in self.model.lower()

    def _rewrite_prompt(
        self,
        prompt: str,
        scene_characters: list,
        tag_prefix: str | None = None,
    ) -> str:
        """Rewrite @character_id tokens in a prompt.

        For O3 clip models: replaces @char_id with @ElementN (1-indexed).
        For O1 Image still models: replaces @char_id with @ImageN (1-indexed).
        For Flux 2 Pro: replaces @char_id with @imageN (1-indexed, lowercase).
        For all other models: strips the @ prefix from @char_id tokens.

        When a tag_prefix is active and no @char_id tokens are found,
        auto-prepends @TagN descriptions using each character's description field.

        Args:
            prompt: Original prompt with possible @character_id tokens.
            scene_characters: Ordered list of Character objects.
            tag_prefix: Explicit tag prefix (e.g. "image" for Flux 2 Pro).
                If None, auto-detects from model type.

        Returns:
            Rewritten prompt.
        """
        char_ids = [c.id for c in scene_characters]

        # Determine the tag prefix based on model type (if not explicit)
        if tag_prefix is None:
            if self._is_o3:
                tag_prefix = "Element"
            elif self._is_o1_image:
                tag_prefix = "Image"

        if tag_prefix:
            # Check if any @character_id tokens are present
            has_tokens = any(
                re.search(rf"@{re.escape(cid)}\b", prompt, flags=re.IGNORECASE)
                for cid in char_ids
            )

            if has_tokens:
                # Replace @char_id with @TagN
                for idx, cid in enumerate(char_ids, start=1):
                    prompt = re.sub(
                        rf"@{re.escape(cid)}\b",
                        f"@{tag_prefix}{idx}",
                        prompt,
                        flags=re.IGNORECASE,
                    )
            else:
                # Auto-prepend @TagN descriptions
                prepend_lines = []
                for idx, char in enumerate(scene_characters, start=1):
                    prepend_lines.append(
                        f"@{tag_prefix}{idx} is {char.description.strip()}."
                    )
                prompt = "\n".join(prepend_lines) + "\n" + prompt
        else:
            # All other models: strip @ prefix from character tokens
            for cid in char_ids:
                prompt = re.sub(
                    rf"@({re.escape(cid)})\b",
                    r"\1",
                    prompt,
                    flags=re.IGNORECASE,
                )

        return prompt

    def _upload_all_references(
        self,
        reference_images: list[Path],
    ) -> list[str]:
        """Upload all valid reference images to FAL CDN.

        Unlike _upload_reference() which uses only the first image,
        this uploads every existing file and returns all URLs.
        Used by O1 Image, Kontext Multi, and EditHandler models.

        Uploads fresh on every call — FAL CDN URLs expire at their
        discretion, so caching is not safe (#123).

        Args:
            reference_images: List of reference image paths.

        Returns:
            List of CDN URL strings for existing files.
        """
        urls = []
        for ref_path in reference_images:
            if ref_path.exists():
                url = fal_client.upload_file(str(ref_path))
                logger.info("Uploaded %s -> %s", ref_path.name, url)
                urls.append(url)
        return urls

    def _build_elements(self, scene_characters: list) -> list[dict]:
        """Build O3 elements array from Character objects.

        For each character with reference images:
        - First reference → frontal_image_url
        - Additional references → reference_image_urls

        Characters without references are skipped.
        Uploads fresh on every call (#123).

        Args:
            scene_characters: Ordered list of Character objects.

        Returns:
            List of element dicts for the O3 API.
        """
        elements = []
        for char in scene_characters:
            existing_refs = [r for r in char.reference if r.exists()]
            if not existing_refs:
                continue

            frontal_url = fal_client.upload_file(str(existing_refs[0]))
            logger.info("Uploaded %s -> %s", existing_refs[0].name, frontal_url)
            extra_urls = []
            for r in existing_refs[1:]:
                url = fal_client.upload_file(str(r))
                logger.info("Uploaded %s -> %s", r.name, url)
                extra_urls.append(url)
            element: dict = {
                "frontal_image_url": frontal_url,
                "reference_image_urls": extra_urls,
            }

            elements.append(element)
        return elements

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

    def _build_clip_args(
        self,
        prompt: str,
        aspect_ratio: str,
        duration: float,
        source_frame_url: str | None,
        last_frame_url: str | None,
        reference_images: list[Path] | None,
        scene_characters: list | None,
        project_dir: Path | None,
    ) -> dict:
        """Build model-specific arguments for clip generation.

        Dispatches to the appropriate argument builder based on the model
        family (Grok, Seedance, Hunyuan, Wan, MiniMax, or Kling).
        """
        if self._is_grok_video:
            arguments: dict = {
                "prompt": prompt,
                "duration": int(duration),
                "aspect_ratio": aspect_ratio,
            }
            if source_frame_url:
                arguments["image_url"] = source_frame_url
        elif self._is_seedance:
            arguments = {
                "prompt": prompt,
                "duration": str(int(duration)),
                "aspect_ratio": aspect_ratio,
                "generate_audio": False,
                "enable_safety_checker": False,
            }
            if source_frame_url:
                arguments["image_url"] = source_frame_url
            if last_frame_url:
                arguments["end_image_url"] = last_frame_url
        elif self._is_hunyuan_video:
            arguments = {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
            }
            if source_frame_url:
                arguments["image_url"] = source_frame_url
        elif self._is_wan:
            arguments = {
                "prompt": prompt,
                "enable_safety_checker": False,
            }
            if source_frame_url:
                arguments["image_url"] = source_frame_url
        elif self._is_minimax:
            arguments = {"prompt": prompt}
            ref_url = self._upload_reference(reference_images)
            if ref_url:
                arguments["subject_reference_image_url"] = ref_url
        else:
            # Kling models
            arguments = self._build_video_args(
                prompt, aspect_ratio, duration, source_frame_url, last_frame_url
            )
            # Build O3 character elements (#37)
            if self._is_o3 and scene_characters:
                elements = self._build_elements(scene_characters)
                if elements:
                    arguments["elements"] = elements
        return arguments

    def _auto_route_clip_endpoint(self, source_frame_url: str | None) -> str:
        """Auto-route clip endpoint between t2v and i2v based on source_frame."""
        endpoint = self.model
        if not self._is_wan and not self._is_minimax:
            has_source = source_frame_url is not None
            if has_source and "text-to-video" in endpoint:
                endpoint = endpoint.replace("text-to-video", "image-to-video")
                logger.info("Auto-routed endpoint to image-to-video (source_frame set)")
            elif not has_source and "image-to-video" in endpoint:
                endpoint = endpoint.replace("image-to-video", "text-to-video")
                logger.info("Auto-routed endpoint to text-to-video (no source_frame)")
        return endpoint

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
        """Generate a video clip via FAL video models.

        Uses fal_client.subscribe() for synchronous generation.
        Supports Kling (with O3 elements), Wan (image-to-video),
        and MiniMax (subject reference) models.

        Raises:
            NotImplementedError: If model is not a video model (e.g. Flux/Kontext).
            RuntimeError: On generation failure.
            ImportError: If fal-client is not installed.
        """
        if not self._is_video_model:
            raise NotImplementedError(
                f"FAL provider ({self.model}) does not support video generation. "
                f"Use a Kling, Wan, MiniMax, Grok, Seedance, or Hunyuan model, "
                f"or Google (Veo) for clips."
            )

        if fal_client is None:
            raise ImportError(
                "fal-client is not installed. Run: pip install fal-client"
            )

        # Rewrite @character_id tokens in prompt (#37)
        if scene_characters:
            prompt = self._rewrite_prompt(prompt, scene_characters)

        # Upload source_frame and last_frame to CDN
        source_frame_url = None
        if source_frame is not None and source_frame.exists():
            source_frame_url = fal_client.upload_file(str(source_frame))
            logger.info("Uploaded source frame -> %s", source_frame_url)

        last_frame_url = None
        if last_frame is not None and last_frame.exists():
            last_frame_url = fal_client.upload_file(str(last_frame))
            logger.info("Uploaded last frame -> %s", last_frame_url)

        arguments = self._build_clip_args(
            prompt,
            aspect_ratio,
            duration,
            source_frame_url,
            last_frame_url,
            reference_images,
            scene_characters,
            project_dir,
        )

        # Merge provider options (cfg_scale, negative_prompt, etc.)
        merged_options = self.options.copy()
        if options:
            merged_options.update(options)
        arguments.update(merged_options)

        endpoint = self._auto_route_clip_endpoint(source_frame_url)

        logger.info(
            "Generating clip via FAL model=%s endpoint=%s", self.model, endpoint
        )
        logger.debug("Arguments: %s", arguments)

        try:
            result = fal_client.subscribe(endpoint, arguments=arguments)
        except (
            Exception
        ) as exc:  # FAL SDK may raise any type; log trace, re-raise clean
            logger.error(
                "FAL clip API error for %s: %s", self.model, exc, exc_info=True
            )
            raise RuntimeError(f"FAL API error: {clean_api_error(str(exc))}") from exc

        video = result.get("video")
        if not video or not video.get("url"):
            raise RuntimeError(
                f"No video generated. The FAL {self.model} safety filter likely "
                f"rejected the prompt or source image. Try revising them."
            )

        video_url = video["url"]
        logger.info("Downloading generated video from %s", video_url)
        return [_download_url(video_url)]
