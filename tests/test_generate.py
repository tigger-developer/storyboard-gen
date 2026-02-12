# ABOUTME: Tests for storyboard_gen.generate.
# ABOUTME: Mocks external Google GenAI API calls (acceptable per TESTING.md).

import io
from unittest.mock import MagicMock

import pytest
from PIL import Image as PILImage

from storyboard_gen.generate import (
    IMAGEN_CAPABILITY_MODEL,
    crop_to_aspect_ratio,
    generate_still,
)
from storyboard_gen.models import Character, Project, Scene


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


class TestGenerateStill:
    def test_generate_still_saves_image(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)

        mock_image = MagicMock()
        mock_image.image.image_bytes = b"fake-png-bytes"
        mock_response = MagicMock()
        mock_response.generated_images = [mock_image]

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response

        # Act
        result = generate_still(scene, project, tmp_path, client=mock_client)

        # Assert
        assert result.exists()
        assert result.name == "scene_01.png"
        assert result.read_bytes() == b"fake-png-bytes"

    def test_generate_still_calls_api_with_correct_prompt(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = b"x"

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response

        # Act
        generate_still(scene, project, tmp_path, client=mock_client)

        # Assert
        call_args = mock_client.models.generate_images.call_args
        assert "Test style." in call_args.kwargs["prompt"]
        assert "A thing." in call_args.kwargs["prompt"]

    def test_generate_still_uses_correct_aspect_ratio(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = b"x"

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response

        # Act
        generate_still(scene, project, tmp_path, client=mock_client)

        # Assert
        call_args = mock_client.models.generate_images.call_args
        assert call_args.kwargs["config"].aspect_ratio == "9:16"

    def test_generate_still_raises_for_clip_scene(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(2)  # clip scene

        # Act & Assert
        with pytest.raises(ValueError, match="not 'still'"):
            generate_still(scene, project, tmp_path)

    def test_generate_still_raises_when_api_returns_no_images(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)

        mock_response = MagicMock()
        mock_response.generated_images = []

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response

        # Act & Assert
        with pytest.raises(RuntimeError, match="No image generated"):
            generate_still(scene, project, tmp_path, client=mock_client)

    def test_generate_still_creates_stills_directory(self, tmp_path):
        # Arrange
        project = _make_project()
        scene = project.get_scene(1)

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = b"x"

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response

        output_dir = tmp_path / "fresh"

        # Act
        generate_still(scene, project, output_dir, client=mock_client)

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

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = b"new-image"

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response

        # Act
        result = generate_still(scene, project, tmp_path, client=mock_client)

        # Assert — new image written
        assert result.read_bytes() == b"new-image"
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

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = b"new-image"

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response

        # Act
        generate_still(scene, project, tmp_path, client=mock_client)

        # Assert — no archive directory created
        assert not (tmp_path / "stills" / "archive").exists()


class TestGenerateStillWithReferences:
    def _make_single_char_project(self, tmp_path):
        """Create a project with one character scene and reference on disk."""
        ref_path = tmp_path / "references" / "hero.png"
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_bytes(b"fake-png-data")

        chars = {
            "hero": Character(
                id="hero", description="A boy with red hair", reference=ref_path
            ),
        }
        scenes = [
            Scene(
                number=1,
                title="Solo hero",
                scene_type="still",
                prompt="Hero stands on a hill.",
                duration=5,
                characters=["hero"],
            ),
        ]
        return Project(
            title="RefTest",
            aspect_ratio="9:16",
            style_prefix="Test style.",
            characters=chars,
            scenes=scenes,
        )

    def test_generate_still_uses_edit_image_for_single_ref_scene(self, tmp_path):
        # Arrange
        project = self._make_single_char_project(tmp_path)
        scene = project.get_scene(1)

        png_bytes = _make_png_bytes()
        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = png_bytes

        mock_client = MagicMock()
        mock_client.models.edit_image.return_value = mock_response

        output_dir = tmp_path / "output"

        # Act
        result = generate_still(scene, project, output_dir, client=mock_client)

        # Assert — edit_image was called, not generate_images
        mock_client.models.edit_image.assert_called_once()
        mock_client.models.generate_images.assert_not_called()
        assert result.exists()

    def test_generate_still_passes_subject_reference_for_single_char(self, tmp_path):
        # Arrange
        project = self._make_single_char_project(tmp_path)
        scene = project.get_scene(1)

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = _make_png_bytes()

        mock_client = MagicMock()
        mock_client.models.edit_image.return_value = mock_response

        # Act
        generate_still(scene, project, tmp_path / "output", client=mock_client)

        # Assert
        call_args = mock_client.models.edit_image.call_args
        assert call_args.kwargs["model"] == IMAGEN_CAPABILITY_MODEL
        ref_images = call_args.kwargs["reference_images"]
        assert len(ref_images) == 1

    def test_generate_still_uses_generate_images_for_multi_char_scene(self, tmp_path):
        # Arrange — multi-character scene should NOT use edit_image
        # to avoid reference bleeding across characters
        ref_path = tmp_path / "references" / "hero.png"
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_bytes(b"fake-png-data")

        chars = {
            "hero": Character(id="hero", description="A boy", reference=ref_path),
            "sidekick": Character(id="sidekick", description="A woman", reference=None),
        }
        scene = Scene(
            number=1,
            title="Group shot",
            scene_type="still",
            prompt="Two people.",
            duration=5,
            characters=["hero", "sidekick"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters=chars,
            scenes=[scene],
        )

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = b"x"

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response

        # Act
        generate_still(scene, project, tmp_path / "output", client=mock_client)

        # Assert — falls back to generate_images for multi-character scenes
        mock_client.models.generate_images.assert_called_once()
        mock_client.models.edit_image.assert_not_called()

    def test_generate_still_raises_when_edit_image_returns_no_images(self, tmp_path):
        # Arrange — edit_image returns empty (safety filter)
        project = self._make_single_char_project(tmp_path)
        scene = project.get_scene(1)

        empty_response = MagicMock()
        empty_response.generated_images = []

        mock_client = MagicMock()
        mock_client.models.edit_image.return_value = empty_response

        # Act & Assert — should fail loud with safety filter hint
        with pytest.raises(RuntimeError, match="safety filter"):
            generate_still(scene, project, tmp_path / "output", client=mock_client)

    def test_generate_still_falls_back_to_generate_images_without_refs(self, tmp_path):
        # Arrange — project with characters but no reference files on disk
        chars = {
            "hero": Character(id="hero", description="A boy", reference=None),
        }
        scene = Scene(
            number=1,
            title="No ref",
            scene_type="still",
            prompt="A thing.",
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

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = b"x"

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_response

        # Act
        generate_still(scene, project, tmp_path / "output", client=mock_client)

        # Assert — falls back to generate_images
        mock_client.models.generate_images.assert_called_once()
        mock_client.models.edit_image.assert_not_called()


class TestCropToAspectRatio:
    def test_crop_landscape_to_portrait(self):
        # Arrange — 1920x1080 landscape image
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (1920, 1080), color="red")

        # Act — crop to 9:16
        result = crop_to_aspect_ratio(img, "9:16")

        # Assert — should be portrait, centred crop
        w, h = result.size
        assert abs(w / h - 9 / 16) < 0.01

    def test_crop_preserves_correct_aspect_already(self):
        # Arrange — already 9:16
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (1080, 1920), color="blue")

        # Act
        result = crop_to_aspect_ratio(img, "9:16")

        # Assert — unchanged
        assert result.size == (1080, 1920)

    def test_crop_square_to_portrait(self):
        # Arrange — 1024x1024 square
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (1024, 1024), color="green")

        # Act
        result = crop_to_aspect_ratio(img, "9:16")

        # Assert — cropped to portrait
        w, h = result.size
        assert abs(w / h - 9 / 16) < 0.01
        # Width should be reduced, height stays
        assert h == 1024
