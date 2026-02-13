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
    """A named character with a description and optional reference image."""

    id: str
    description: str
    reference: Path | None = None


@dataclass(frozen=True)
class Scene:
    """A single scene in the storyboard."""

    number: int
    title: str
    scene_type: str  # "still" or "clip"
    prompt: str
    duration: int  # seconds
    camera: str | None = None  # WIDE, CLOSE, WINDOW, etc.
    ken_burns: str | None = None  # zoom_in, zoom_out, pan_ltr, pan_rtl, static
    characters: list[str] = field(default_factory=list)  # character IDs
    provider: ProviderConfig | None = None  # per-scene provider override
    model: str | None = None  # per-scene model-only override (shorthand)


VALID_SCENE_TYPES = {"still", "clip"}
VALID_KEN_BURNS = {"zoom_in", "zoom_out", "pan_ltr", "pan_rtl", "static", None}
VALID_ASPECT_RATIOS = {"9:16", "16:9", "4:3", "1:1"}


@dataclass(frozen=True)
class Project:
    """A complete storyboard project loaded from project.yaml."""

    title: str
    aspect_ratio: str
    style_prefix: str
    characters: dict[str, Character]
    scenes: list[Scene]
    still_provider: ProviderConfig | None = None
    clip_provider: ProviderConfig | None = None

    def get_scene(self, number: int) -> Scene:
        """Return a scene by number. Raises ValueError if not found."""
        for scene in self.scenes:
            if scene.number == number:
                return scene
        raise ValueError(f"No scene with number {number}")

    def get_stills(self) -> list[Scene]:
        """Return all scenes of type 'still'."""
        return [s for s in self.scenes if s.scene_type == "still"]

    def get_clips(self) -> list[Scene]:
        """Return all scenes of type 'clip'."""
        return [s for s in self.scenes if s.scene_type == "clip"]

    def build_prompt(self, scene: Scene) -> str:
        """Prepend the style prefix to a scene's prompt."""
        return f"{self.style_prefix.strip()} {scene.prompt.strip()}"

    def get_reference_images(self, scene: Scene) -> list[Path]:
        """Return reference image paths for characters in a scene."""
        refs = []
        for char_id in scene.characters:
            char = self.characters.get(char_id)
            if char and char.reference and char.reference.exists():
                refs.append(char.reference)
        return refs
