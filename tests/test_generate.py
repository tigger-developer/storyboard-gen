# ABOUTME: Tests for storyboard_gen.generate orchestrator.
# ABOUTME: Uses mock providers to test orchestration logic (acceptable per TESTING.md).

import io
from unittest.mock import MagicMock

import pytest
from PIL import Image as PILImage

from storyboard_gen.generate import (
    _resolve_provider,
    crop_to_aspect_ratio,
    generate_clip,
    generate_still,
)
from storyboard_gen.models import Character, Project, ProviderConfig, Scene
from storyboard_gen.providers.base import ImageProvider


def _make_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """Create valid PNG bytes for testing."""
    img = PILImage.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_project(**overrides) -> Project:
    """Create a test project with optional scene overrides."""
    scenes = overrides.pop("scenes", None)
    if scenes is None:
        scenes = [
            Scene(
                number="1",
                title="Still",
                scene_type="still",
                prompt="A thing.",
                duration=5,
            ),
            Scene(
                number="2",
                title="Clip",
                scene_type="clip",
                prompt="Action.",
                duration=6,
            ),
        ]
    defaults = {
        "title": "Test",
        "aspect_ratio": "9:16",
        "style_prefix": "Test style.",
        "characters": {},
        "scenes": scenes,
    }
    defaults.update(overrides)
    return Project(**defaults)


def _make_mock_provider(image_bytes: bytes | None = None) -> MagicMock:
    """Create a mock provider that returns the given image bytes."""
    provider = MagicMock(spec=ImageProvider)
    provider.options = {}
    if image_bytes is None:
        image_bytes = _make_png_bytes()
    provider.generate_still.return_value = image_bytes
    provider.generate_clip.return_value = [b"video-bytes"]
    return provider


class TestGenerateStill:
    def test_generate_still_saves_image(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)
        png = _make_png_bytes()
        provider = _make_mock_provider(png)

        # Act
        result = generate_still(scene, project, tmp_path, provider=provider)

        # Assert
        assert result.exists()
        assert result.name == "scene_01.png"

    def test_generate_still_calls_provider_with_correct_prompt(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)
        provider = _make_mock_provider()

        # Act
        generate_still(scene, project, tmp_path, provider=provider)

        # Assert
        call_args = provider.generate_still.call_args
        assert "Test style." in call_args.kwargs["prompt"]
        assert "A thing." in call_args.kwargs["prompt"]

    def test_generate_still_passes_correct_aspect_ratio(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)
        provider = _make_mock_provider()

        # Act
        generate_still(scene, project, tmp_path, provider=provider)

        # Assert
        call_args = provider.generate_still.call_args
        assert call_args.kwargs["aspect_ratio"] == "9:16"

    def test_generate_still_raises_for_clip_scene(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(2)  # clip scene
        provider = _make_mock_provider()

        # Act & Assert
        with pytest.raises(ValueError, match="not 'still'"):
            generate_still(scene, project, tmp_path, provider=provider)

    def test_generate_still_creates_stills_directory(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)
        provider = _make_mock_provider()
        output_dir = tmp_path / "fresh"

        # Act
        generate_still(scene, project, output_dir, provider=provider)

        # Assert
        assert (output_dir / "stills").is_dir()

    def test_generate_still_archives_existing_image(self, tmp_path):
        # Arrange — pre-existing still on disk
        project = _make_project()
        scene = project.get_scene(1)

        stills_dir = tmp_path / "stills"
        stills_dir.mkdir(parents=True)
        existing = stills_dir / "scene_01.png"
        existing.write_bytes(b"old-image")

        provider = _make_mock_provider()

        # Act
        result = generate_still(scene, project, tmp_path, provider=provider)

        # Assert — new image written
        assert result.exists()
        # Assert — old image archived
        archive_dir = stills_dir / "archive"
        assert archive_dir.is_dir()
        archived = list(archive_dir.glob("scene_01_*.png"))
        assert len(archived) == 1
        assert archived[0].read_bytes() == b"old-image"

    def test_generate_still_does_not_archive_when_no_existing_image(self, tmp_path):
        # Arrange — no pre-existing still
        project = _make_project()
        scene = project.get_scene(1)
        provider = _make_mock_provider()

        # Act
        generate_still(scene, project, tmp_path, provider=provider)

        # Assert — no archive directory created
        assert not (tmp_path / "stills" / "archive").exists()

    def test_generate_still_passes_reference_images(self, tmp_path):
        # Arrange — project with a character that has a reference on disk
        ref_path = tmp_path / "references" / "hero.png"
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_bytes(b"fake-png-data")

        chars = {
            "hero": Character(
                id="hero", description="A boy with red hair", reference=[ref_path]
            ),
        }
        scene = Scene(
            number="1",
            title="Solo hero",
            scene_type="still",
            prompt="Hero stands.",
            duration=5,
            characters=["hero"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters=chars,
            scenes=[scene],
        )
        provider = _make_mock_provider()

        # Act
        generate_still(scene, project, tmp_path / "output", provider=provider)

        # Assert — reference images passed to provider
        call_args = provider.generate_still.call_args
        assert call_args.kwargs["reference_images"] == [ref_path]


class TestResolveProvider:
    def test_resolve_provider_scene_model_overrides_project_provider(self, monkeypatch):
        # Arrange — project has fal/flux-general, scene overrides model only
        scene = Scene(
            number="1",
            title="Kontext",
            scene_type="still",
            prompt="A portrait.",
            duration=5,
            model="fal-ai/flux-pro/kontext",
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters={},
            scenes=[scene],
            still_provider=ProviderConfig(
                backend="fal",
                model="fal-ai/flux-general",
                options={"safety_tolerance": 5},
            ),
        )
        captured = {}
        mock_provider = _make_mock_provider()

        def fake_create(backend, model, options):
            captured["backend"] = backend
            captured["model"] = model
            captured["options"] = options
            return mock_provider

        monkeypatch.setattr("storyboard_gen.generate.create_provider", fake_create)

        # Act
        _resolve_provider(scene, project, "still")

        # Assert — model from scene, backend and options from project provider
        assert captured["model"] == "fal-ai/flux-pro/kontext"
        assert captured["backend"] == "fal"
        assert captured["options"] == {"safety_tolerance": 5}

    def test_resolve_provider_scene_model_without_project_provider_uses_google_default(
        self, monkeypatch
    ):
        # Arrange — no project-level provider, scene overrides model only
        scene = Scene(
            number="1",
            title="Custom model",
            scene_type="still",
            prompt="x",
            duration=5,
            model="imagen-5.0-generate-001",
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters={},
            scenes=[scene],
        )
        captured = {}
        mock_provider = _make_mock_provider()

        def fake_create(backend, model, options):
            captured["backend"] = backend
            captured["model"] = model
            captured["options"] = options
            return mock_provider

        monkeypatch.setattr("storyboard_gen.generate.create_provider", fake_create)

        # Act
        _resolve_provider(scene, project, "still")

        # Assert — model from scene, backend defaults to google
        assert captured["model"] == "imagen-5.0-generate-001"
        assert captured["backend"] == "google"


class TestCropToAspectRatio:
    def test_crop_landscape_to_portrait(self):
        # Arrange — 1920x1080 landscape image
        img = PILImage.new("RGB", (1920, 1080), color="red")

        # Act — crop to 9:16
        result = crop_to_aspect_ratio(img, "9:16")

        # Assert — should be portrait, centred crop
        w, h = result.size
        assert abs(w / h - 9 / 16) < 0.01

    def test_crop_preserves_correct_aspect_already(self):
        # Arrange — already 9:16
        img = PILImage.new("RGB", (1080, 1920), color="blue")

        # Act
        result = crop_to_aspect_ratio(img, "9:16")

        # Assert — unchanged
        assert result.size == (1080, 1920)

    def test_crop_square_to_portrait(self):
        # Arrange — 1024x1024 square
        img = PILImage.new("RGB", (1024, 1024), color="green")

        # Act
        result = crop_to_aspect_ratio(img, "9:16")

        # Assert — cropped to portrait
        w, h = result.size
        assert abs(w / h - 9 / 16) < 0.01
        # Width should be reduced, height stays
        assert h == 1024


class TestGenerateClip:
    def test_generate_clip_saves_video(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(2)
        provider = _make_mock_provider()

        # Act
        result = generate_clip(scene, project, tmp_path, provider=provider)

        # Assert
        assert result.exists()
        assert result.name == "scene_02.mp4"
        assert result.read_bytes() == b"video-bytes"

    def test_generate_clip_raises_for_still_scene(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)  # still scene
        provider = _make_mock_provider()

        # Act & Assert
        with pytest.raises(ValueError, match="not 'clip'"):
            generate_clip(scene, project, tmp_path, provider=provider)

    def test_generate_clip_passes_correct_prompt(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(2)
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert
        call_args = provider.generate_clip.call_args
        assert "Test style." in call_args.kwargs["prompt"]
        assert "Action." in call_args.kwargs["prompt"]

    def test_generate_clip_archives_existing(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(2)
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir(parents=True)
        existing = clips_dir / "scene_02.mp4"
        existing.write_bytes(b"old-video")
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — old clip archived
        archive_dir = clips_dir / "archive"
        assert archive_dir.is_dir()
        archived = list(archive_dir.glob("scene_02_*.mp4"))
        assert len(archived) == 1
        assert archived[0].read_bytes() == b"old-video"

    def test_generate_clip_passes_source_frame(self, tmp_path):
        # Arrange — scene with source_frame
        frame = tmp_path / "frame.png"
        frame.write_bytes(b"fake-frame")
        scene = Scene(
            number="1",
            title="Animated",
            scene_type="clip",
            prompt="Animate.",
            duration=5,
            source_frame=frame,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — source_frame passed to provider
        call_kwargs = provider.generate_clip.call_args.kwargs
        assert call_kwargs["source_frame"] == frame

    def test_generate_clip_passes_last_frame(self, tmp_path):
        # Arrange
        first = tmp_path / "first.png"
        first.write_bytes(b"fake-first")
        last = tmp_path / "last.png"
        last.write_bytes(b"fake-last")
        scene = Scene(
            number="1",
            title="Interpolated",
            scene_type="clip",
            prompt="Interpolate.",
            duration=5,
            source_frame=first,
            last_frame=last,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert
        call_kwargs = provider.generate_clip.call_args.kwargs
        assert call_kwargs["last_frame"] == last

    def test_generate_clip_passes_seed(self, tmp_path):
        # Arrange
        scene = Scene(
            number="1",
            title="Seeded",
            scene_type="clip",
            prompt="Deterministic.",
            duration=5,
            seed=42,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert
        call_kwargs = provider.generate_clip.call_args.kwargs
        assert call_kwargs["seed"] == 42

    def test_generate_clip_passes_number_of_videos(self, tmp_path):
        # Arrange
        scene = Scene(
            number="1",
            title="Multi",
            scene_type="clip",
            prompt="Multi.",
            duration=5,
            variants=3,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()
        provider.generate_clip.return_value = [b"v0", b"v1", b"v2"]

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert
        call_kwargs = provider.generate_clip.call_args.kwargs
        assert call_kwargs["number_of_videos"] == 3


class TestSceneCharactersPassthrough:
    """Tests for passing scene_characters to providers (#37)."""

    def test_generate_clip_passes_scene_characters(self, tmp_path):
        """generate_clip should resolve characters and pass them to the provider."""
        # Arrange
        chars = {
            "boy": Character(
                id="boy", description="A boy with curly hair", reference=[]
            ),
            "mum": Character(
                id="mum", description="A woman with dark hair", reference=[]
            ),
        }
        scene = Scene(
            number="1",
            title="Together",
            scene_type="clip",
            prompt="@boy and @mum walk.",
            duration=5,
            characters=["boy", "mum"],
        )
        project = _make_project(characters=chars, scenes=[scene])
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — scene_characters passed in correct order
        call_kwargs = provider.generate_clip.call_args.kwargs
        scene_chars = call_kwargs["scene_characters"]
        assert len(scene_chars) == 2
        assert scene_chars[0].id == "boy"
        assert scene_chars[1].id == "mum"

    def test_generate_clip_no_characters_passes_none(self, tmp_path):
        """generate_clip with no characters should pass empty/None."""
        # Arrange
        scene = Scene(
            number="1",
            title="Solo",
            scene_type="clip",
            prompt="A landscape.",
            duration=5,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — no scene_characters (empty list → None)
        call_kwargs = provider.generate_clip.call_args.kwargs
        assert not call_kwargs.get("scene_characters")

    def test_generate_clip_skips_unknown_character_ids(self, tmp_path):
        """Unknown character IDs in scene.characters should be skipped."""
        # Arrange
        chars = {
            "boy": Character(id="boy", description="A boy", reference=[]),
        }
        scene = Scene(
            number="1",
            title="Mixed",
            scene_type="clip",
            prompt="Action.",
            duration=5,
            characters=["boy", "ghost"],  # ghost not in project.characters
        )
        project = _make_project(characters=chars, scenes=[scene])
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — only known character passed
        call_kwargs = provider.generate_clip.call_args.kwargs
        scene_chars = call_kwargs["scene_characters"]
        assert len(scene_chars) == 1
        assert scene_chars[0].id == "boy"


class TestExtendFromResolution:
    def test_extend_from_resolves_clips_dir(self, tmp_path):
        """extend_from should find the clip in output/clips/."""
        # Arrange — existing clip
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir(parents=True)
        existing_clip = clips_dir / "scene_01.mp4"
        existing_clip.write_bytes(b"prev-clip")

        scene = Scene(
            number="2",
            title="Continue",
            scene_type="clip",
            prompt="Continue.",
            duration=5,
            extend_from="1",
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — resolved path passed to provider
        call_kwargs = provider.generate_clip.call_args.kwargs
        assert call_kwargs["extend_from_video"] == existing_clip

    def test_extend_from_resolves_intermediate_dir(self, tmp_path):
        """extend_from should fall back to output/intermediate/."""
        # Arrange — no clips/, but intermediate/ exists
        intermediate_dir = tmp_path / "intermediate"
        intermediate_dir.mkdir(parents=True)
        existing_clip = intermediate_dir / "scene_01.mp4"
        existing_clip.write_bytes(b"prev-intermediate")

        scene = Scene(
            number="2",
            title="Continue",
            scene_type="clip",
            prompt="Continue.",
            duration=5,
            extend_from="1",
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert
        call_kwargs = provider.generate_clip.call_args.kwargs
        assert call_kwargs["extend_from_video"] == existing_clip

    def test_extend_from_not_found_raises(self, tmp_path):
        """RuntimeError when extended scene's clip is not found."""
        # Arrange — no existing clip at all
        scene = Scene(
            number="2",
            title="Continue",
            scene_type="clip",
            prompt="Continue.",
            duration=5,
            extend_from="1",
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()

        # Act & Assert
        with pytest.raises(RuntimeError, match="Cannot extend from scene 1"):
            generate_clip(scene, project, tmp_path, provider=provider)

    def test_extend_from_without_extend_passes_none(self, tmp_path):
        """When extend_from is not set, extend_from_video should be None."""
        # Arrange
        scene = Scene(
            number="1",
            title="Normal",
            scene_type="clip",
            prompt="Normal.",
            duration=5,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert
        call_kwargs = provider.generate_clip.call_args.kwargs
        assert call_kwargs["extend_from_video"] is None


class TestVariantFileNaming:
    def test_single_variant_saves_bare_file(self, tmp_path):
        """variants=1 (default) saves as bare scene_01.mp4."""
        # Arrange
        scene = Scene(
            number="1",
            title="Single",
            scene_type="clip",
            prompt="Action.",
            duration=5,
            variants=1,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()
        provider.generate_clip.return_value = [b"video-bytes"]

        # Act
        result = generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — bare file, no variant suffix
        assert result.name == "scene_01.mp4"
        assert result.read_bytes() == b"video-bytes"
        # No variant files
        clips_dir = tmp_path / "clips"
        assert not list(clips_dir.glob("scene_01_v*.mp4"))

    def test_multiple_variants_saves_with_suffix(self, tmp_path):
        """variants>1 saves as scene_01_v0.mp4, scene_01_v1.mp4, etc."""
        # Arrange
        scene = Scene(
            number="1",
            title="Multi",
            scene_type="clip",
            prompt="Action.",
            duration=5,
            variants=2,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()
        provider.generate_clip.return_value = [b"video-v0", b"video-v1"]

        # Act
        result = generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — variant files exist
        clips_dir = tmp_path / "clips"
        v0 = clips_dir / "scene_01_v0.mp4"
        v1 = clips_dir / "scene_01_v1.mp4"
        assert v0.exists()
        assert v1.exists()
        assert v0.read_bytes() == b"video-v0"
        assert v1.read_bytes() == b"video-v1"
        # No bare file
        assert not (clips_dir / "scene_01.mp4").exists()
        # Return first variant
        assert result == v0

    def test_multiple_variants_archives_existing_variants(self, tmp_path):
        """Re-running generation archives existing variant files."""
        # Arrange — pre-existing variant files
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir(parents=True)
        (clips_dir / "scene_01_v0.mp4").write_bytes(b"old-v0")
        (clips_dir / "scene_01_v1.mp4").write_bytes(b"old-v1")

        scene = Scene(
            number="1",
            title="Multi",
            scene_type="clip",
            prompt="Action.",
            duration=5,
            variants=2,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()
        provider.generate_clip.return_value = [b"new-v0", b"new-v1"]

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — old variants archived
        archive_dir = clips_dir / "archive"
        assert archive_dir.is_dir()
        archived = list(archive_dir.glob("scene_01_v*_*.mp4"))
        assert len(archived) == 2

        # New variants in place
        assert (clips_dir / "scene_01_v0.mp4").read_bytes() == b"new-v0"
        assert (clips_dir / "scene_01_v1.mp4").read_bytes() == b"new-v1"

    def test_multiple_variants_archives_existing_bare_file(self, tmp_path):
        """Re-running with variants>1 also archives an existing bare file."""
        # Arrange — bare file from previous run with variants=1
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir(parents=True)
        (clips_dir / "scene_01.mp4").write_bytes(b"old-bare")

        scene = Scene(
            number="1",
            title="Multi",
            scene_type="clip",
            prompt="Action.",
            duration=5,
            variants=2,
        )
        project = _make_project(scenes=[scene])
        provider = _make_mock_provider()
        provider.generate_clip.return_value = [b"new-v0", b"new-v1"]

        # Act
        generate_clip(scene, project, tmp_path, provider=provider)

        # Assert — bare file archived
        archive_dir = clips_dir / "archive"
        archived_bare = list(archive_dir.glob("scene_01_*.mp4"))
        # At least one archived bare file (the one without _v suffix)
        assert any("_v" not in f.stem.split("scene_01_", 1)[1] for f in archived_bare)
