# ABOUTME: Tests for storyboard_gen.generate.
# ABOUTME: Mocks external Google GenAI API calls (acceptable per TESTING.md).

from unittest.mock import MagicMock

import pytest

from storyboard_gen.generate import IMAGEN_CAPABILITY_MODEL, generate_still
from storyboard_gen.models import Character, Project, Scene


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


class TestGenerateStillWithReferences:
    def _make_project_with_refs(self, tmp_path):
        """Create a project with character reference images on disk."""
        ref_path = tmp_path / "references" / "hero.png"
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        ref_path.write_bytes(b"fake-png-data")

        chars = {
            "hero": Character(
                id="hero", description="A boy with red hair", reference=ref_path
            ),
            "sidekick": Character(
                id="sidekick", description="A tall woman", reference=None
            ),
        }
        scenes = [
            Scene(
                number=1,
                title="With ref",
                scene_type="still",
                prompt="Hero stands on a hill.",
                duration=5,
                characters=["hero", "sidekick"],
            ),
        ]
        return Project(
            title="RefTest",
            aspect_ratio="9:16",
            style_prefix="Test style.",
            characters=chars,
            scenes=scenes,
        )

    def test_generate_still_uses_edit_image_when_references_exist(self, tmp_path):
        # Arrange
        project = self._make_project_with_refs(tmp_path)
        scene = project.get_scene(1)

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = b"ref-img"

        mock_client = MagicMock()
        mock_client.models.edit_image.return_value = mock_response

        output_dir = tmp_path / "output"

        # Act
        result = generate_still(scene, project, output_dir, client=mock_client)

        # Assert — edit_image was called, not generate_images
        mock_client.models.edit_image.assert_called_once()
        mock_client.models.generate_images.assert_not_called()
        assert result.read_bytes() == b"ref-img"

    def test_generate_still_passes_subject_reference_images(self, tmp_path):
        # Arrange
        project = self._make_project_with_refs(tmp_path)
        scene = project.get_scene(1)

        mock_response = MagicMock()
        mock_response.generated_images = [MagicMock()]
        mock_response.generated_images[0].image.image_bytes = b"x"

        mock_client = MagicMock()
        mock_client.models.edit_image.return_value = mock_response

        # Act
        generate_still(scene, project, tmp_path / "output", client=mock_client)

        # Assert
        call_args = mock_client.models.edit_image.call_args
        assert call_args.kwargs["model"] == IMAGEN_CAPABILITY_MODEL
        ref_images = call_args.kwargs["reference_images"]
        # Only hero has a reference file on disk; sidekick has None
        assert len(ref_images) == 1

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
