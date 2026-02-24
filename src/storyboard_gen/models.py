# ABOUTME: Data models for storyboard-gen.
# ABOUTME: Dataclasses representing a project, its scenes, and characters.

from dataclasses import dataclass, field
from pathlib import Path


VALID_BACKENDS = {"google", "fal", "replicate"}


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for an image/video generation provider."""

    backend: str  # "google", "fal", or "replicate"
    model: str  # provider-specific model identifier
    options: dict = field(default_factory=dict)  # provider-specific options


@dataclass(frozen=True)
class Character:
    """A named character with a description and optional reference images."""

    id: str
    description: str
    reference: list[Path] = field(default_factory=list)


def format_scene_number(number: str) -> str:
    """Format a scene number for use in filenames.

    Purely numeric numbers are zero-padded to 2 digits for backward
    compatibility. Alphanumeric numbers are used as-is.
    """
    if number.isdigit():
        return f"{int(number):02d}"
    return number


@dataclass(frozen=True)
class Scene:
    """A single scene in the storyboard."""

    number: str
    title: str
    scene_type: str  # "still" or "clip"
    prompt: str
    duration: float  # seconds (supports sub-second precision for voice-over alignment)
    camera: str | None = None  # WIDE, CLOSE, WINDOW, etc.
    ken_burns: str | None = None  # zoom_in, zoom_out, pan_ltr, pan_rtl, static
    characters: list[str] = field(default_factory=list)  # character IDs
    provider: ProviderConfig | None = None  # per-scene provider override
    model: str | None = None  # per-scene model-only override (shorthand)
    reference: list[Path] = field(default_factory=list)  # per-scene reference override
    source_frame: Path | None = None  # image-to-video first frame (clips only)
    last_frame: Path | None = None  # interpolation end frame (requires source_frame)
    extend_from: str | None = None  # scene number to extend from (clips only)
    seed: int | None = None  # reproducibility seed
    variants: int = 1  # number of video takes (1-4)


VALID_SCENE_TYPES = {"still", "clip"}
VALID_KEN_BURNS = {"zoom_in", "zoom_out", "pan_ltr", "pan_rtl", "static", None}
VALID_ASPECT_RATIOS = {"9:16", "16:9", "4:3", "1:1"}

# Standard camera values and their prompt phrasings for AI generation.
# Keys are uppercase; lookup in build_prompt() is case-insensitive.
CAMERA_PROMPTS: dict[str, str] = {
    "EWS": "Extreme wide establishing shot showing the full environment.",
    "WIDE": "Wide shot, full body visible in the environment.",
    "MEDIUM": "Medium shot framed from the waist up.",
    "MCU": "Medium close-up framed from the chest up.",
    "CLOSE": "Close-up of the face, tightly framed.",
    "ECU": "Extreme close-up, tightly cropped to a single detail.",
    "POV": "First-person point of view, seen through the character's eyes.",
    "LOW": "Low angle shot looking upward, character appears dominant.",
    "HIGH": "High angle shot looking downward, character appears small.",
    "OVERHEAD": "Bird's-eye overhead shot looking straight down.",
    "OTS": "Over-the-shoulder shot, shallow depth of field, foreground shoulder blurred.",
    "DUTCH": "Camera tilted 20 degrees off-axis, creating unease.",
}
VALID_CAMERAS = set(CAMERA_PROMPTS.keys()) | {None}


@dataclass(frozen=True)
class Project:
    """A complete storyboard project loaded from project.yaml."""

    title: str
    aspect_ratio: str
    style_prefix: str
    characters: dict[str, Character]
    scenes: list[Scene]
    style_reference: list[Path] = field(default_factory=list)
    still_provider: ProviderConfig | None = None
    clip_provider: ProviderConfig | None = None
    audio: Path | None = None

    def get_scene(self, number: str) -> Scene:
        """Return a scene by number. Raises ValueError if not found."""
        lookup = str(number)
        for scene in self.scenes:
            if scene.number == lookup:
                return scene
        raise ValueError(f"No scene with number {number}")

    def get_stills(self) -> list[Scene]:
        """Return all scenes of type 'still'."""
        return [s for s in self.scenes if s.scene_type == "still"]

    def get_clips(self) -> list[Scene]:
        """Return all scenes of type 'clip'."""
        return [s for s in self.scenes if s.scene_type == "clip"]

    def build_prompt(self, scene: Scene) -> str:
        """Build the full prompt: style prefix + camera + characters + scene prompt.

        Camera phrasing is injected from CAMERA_PROMPTS when the scene has a
        camera value. Character descriptions are injected when the scene lists
        characters, providing textual context even when reference images cannot
        be sent.
        """
        parts = [self.style_prefix.strip()]
        if scene.camera is not None:
            camera_key = scene.camera.upper()
            parts.append(CAMERA_PROMPTS[camera_key])
        char_descs = []
        for char_id in scene.characters:
            char = self.characters.get(char_id)
            if char:
                char_descs.append(f"{char.id}: {char.description.strip()}")
        if char_descs:
            parts.append("Characters: " + "; ".join(char_descs) + ".")
        parts.append(scene.prompt.strip())
        return " ".join(parts)

    def get_reference_images(self, scene: Scene) -> list[Path]:
        """Return reference image paths for a scene.

        If the scene has reference overrides, return those (filtering to
        existing paths).  Otherwise fall back to character-level reference
        images, interleaved round-robin across characters so each character
        gets at least one ref before any character gets a second.
        """
        if scene.reference:
            return [r for r in scene.reference if r.exists()]
        per_char = []
        for char_id in scene.characters:
            char = self.characters.get(char_id)
            if char:
                existing = [r for r in char.reference if r.exists()]
                if existing:
                    per_char.append(existing)
        refs = []
        idx = 0
        while True:
            added = False
            for char_refs in per_char:
                if idx < len(char_refs):
                    refs.append(char_refs[idx])
                    added = True
            if not added:
                break
            idx += 1
        return refs
