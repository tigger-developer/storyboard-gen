# ABOUTME: Tests for storyboard_gen.generate.
# ABOUTME: Mocks external Google GenAI API calls (acceptable per TESTING.md).

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from storyboard_gen.generate import generate_still
from storyboard_gen.models import Character, Project, Scene


def _make_project() -> Project:
    """Create a test project."""
    return Project(
        title="Test",
        aspect_ratio="9:16",
        style_prefix="Test style.",
        characters={},
        scenes=[
            Scene(number=1, title="Still", scene_type="still", prompt="A thing.", duration=5),
            Scene(number=2, title="Clip", scene_type="clip", prompt="Action.", duration=6),
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
