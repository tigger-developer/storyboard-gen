# ABOUTME: Tests for storyboard_gen.generate orchestrator.
# ABOUTME: Uses mock providers to test orchestration logic (acceptable per TESTING.md).

import io
from unittest.mock import MagicMock

import pytest
from PIL import Image as PILImage

from storyboard_gen.generate import crop_to_aspect_ratio, generate_still
from storyboard_gen.models import Character, Project, Scene
from storyboard_gen.providers.base import ImageProvider


def _make_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """Create valid PNG bytes for testing."""
    img = PILImage.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_project() -> Project:
    """Create a test project."""
    return Project(
        title="Test",
        aspect_ratio="9:16",
        style_prefix="Test style.",
        characters={},
        scenes=[
            Scene(
                number=1,
                title="Still",
                scene_type="still",
                prompt="A thing.",
                duration=5,
            ),
            Scene(
                number=2, title="Clip", scene_type="clip", prompt="Action.", duration=6
            ),
        ],
    )


def _make_mock_provider(image_bytes: bytes | None = None) -> MagicMock:
    """Create a mock provider that returns the given image bytes."""
    provider = MagicMock(spec=ImageProvider)
    provider.options = {}
    if image_bytes is None:
        image_bytes = _make_png_bytes()
    provider.generate_still.return_value = image_bytes
    provider.generate_clip.return_value = b"video-bytes"
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
                id="hero", description="A boy with red hair", reference=ref_path
            ),
        }
        scene = Scene(
            number=1,
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
