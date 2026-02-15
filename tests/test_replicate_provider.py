# ABOUTME: Tests for the Replicate provider implementation.
# ABOUTME: Mocks replicate SDK calls (external HTTP API — acceptable per TESTING.md).

from unittest.mock import MagicMock, patch

import pytest

from storyboard_gen.providers.replicate import ReplicateProvider


class TestReplicateProviderInit:
    def test_stores_model_and_options(self):
        provider = ReplicateProvider(
            model="black-forest-labs/flux-1.1-pro", options={"seed": 42}
        )
        assert provider.model == "black-forest-labs/flux-1.1-pro"
        assert provider.options == {"seed": 42}

    def test_defaults_empty_options(self):
        provider = ReplicateProvider(model="black-forest-labs/flux-1.1-pro")
        assert provider.options == {}


class TestReplicateGenerateStill:
    @patch("storyboard_gen.providers.replicate.replicate")
    def test_calls_run_with_correct_arguments(self, mock_replicate, tmp_path):
        # Arrange
        mock_output = MagicMock()
        mock_output.read.return_value = b"png-bytes"
        mock_replicate.run.return_value = mock_output
        provider = ReplicateProvider(model="black-forest-labs/flux-1.1-pro")

        # Act
        result = provider.generate_still(
            prompt="A boy in a field",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
        )

        # Assert
        call_args = mock_replicate.run.call_args
        assert call_args.args[0] == "black-forest-labs/flux-1.1-pro"
        input_args = call_args.kwargs["input"]
        assert input_args["prompt"] == "A boy in a field"
        assert input_args["aspect_ratio"] == "9:16"
        assert input_args["output_format"] == "png"
        assert result == b"png-bytes"

    @patch("storyboard_gen.providers.replicate.replicate")
    def test_passes_options_as_input(self, mock_replicate, tmp_path):
        # Arrange
        mock_output = MagicMock()
        mock_output.read.return_value = b"png-bytes"
        mock_replicate.run.return_value = mock_output
        provider = ReplicateProvider(
            model="black-forest-labs/flux-1.1-pro",
            options={"seed": 42, "safety_tolerance": 5},
        )

        # Act
        provider.generate_still(
            prompt="Prompt",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="16:9",
        )

        # Assert — options merged into input
        input_args = mock_replicate.run.call_args.kwargs["input"]
        assert input_args["seed"] == 42
        assert input_args["safety_tolerance"] == 5

    @patch("storyboard_gen.providers.replicate.replicate")
    def test_handles_list_output_from_flux_dev(self, mock_replicate, tmp_path):
        # Arrange — flux-dev returns a list of FileOutput objects
        mock_file = MagicMock()
        mock_file.read.return_value = b"png-bytes"
        mock_replicate.run.return_value = [mock_file]
        provider = ReplicateProvider(model="black-forest-labs/flux-dev")

        # Act
        result = provider.generate_still(
            prompt="A hero",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
        )

        # Assert
        assert result == b"png-bytes"

    @patch("storyboard_gen.providers.replicate.replicate")
    def test_passes_reference_image_for_flux_dev(self, mock_replicate, tmp_path):
        # Arrange
        ref_path = tmp_path / "ref.png"
        ref_path.write_bytes(b"fake-image")

        mock_file = MagicMock()
        mock_file.read.return_value = b"png-bytes"
        mock_replicate.run.return_value = [mock_file]
        provider = ReplicateProvider(model="black-forest-labs/flux-dev")

        # Act
        provider.generate_still(
            prompt="A hero",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=[ref_path],
        )

        # Assert — image parameter should be set
        input_args = mock_replicate.run.call_args.kwargs["input"]
        assert "image" in input_args

    @patch("storyboard_gen.providers.replicate.replicate")
    def test_skips_nonexistent_reference_image(self, mock_replicate, tmp_path):
        # Arrange
        ref_path = tmp_path / "missing.png"

        mock_output = MagicMock()
        mock_output.read.return_value = b"png-bytes"
        mock_replicate.run.return_value = mock_output
        provider = ReplicateProvider(model="black-forest-labs/flux-1.1-pro")

        # Act
        provider.generate_still(
            prompt="A hero",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=[ref_path],
        )

        # Assert — no image in input
        input_args = mock_replicate.run.call_args.kwargs["input"]
        assert "image" not in input_args

    @patch("storyboard_gen.providers.replicate.replicate")
    def test_raises_when_run_raises(self, mock_replicate, tmp_path):
        # Arrange
        mock_replicate.run.side_effect = Exception("API error")
        provider = ReplicateProvider(model="black-forest-labs/flux-1.1-pro")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Replicate API error"):
            provider.generate_still(
                prompt="Prompt",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
            )

    @patch("storyboard_gen.providers.replicate.replicate")
    def test_raises_when_output_is_none(self, mock_replicate, tmp_path):
        # Arrange
        mock_replicate.run.return_value = None
        provider = ReplicateProvider(model="black-forest-labs/flux-1.1-pro")

        # Act & Assert
        with pytest.raises(RuntimeError, match="No image generated"):
            provider.generate_still(
                prompt="Prompt",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
            )


class TestReplicateMultiReference:
    """Tests for multi-reference image handling in Replicate provider."""

    @patch("storyboard_gen.providers.replicate.replicate")
    def test_uses_first_reference_when_multiple_provided(
        self, mock_replicate, tmp_path
    ):
        """Multi-ref scenes should use the first reference, not discard all."""
        # Arrange
        ref1 = tmp_path / "ref1.png"
        ref2 = tmp_path / "ref2.png"
        ref1.write_bytes(b"fake-image-1")
        ref2.write_bytes(b"fake-image-2")

        mock_file = MagicMock()
        mock_file.read.return_value = b"png-bytes"
        mock_replicate.run.return_value = [mock_file]
        provider = ReplicateProvider(model="black-forest-labs/flux-dev")

        # Act
        provider.generate_still(
            prompt="A hero and sidekick",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=[ref1, ref2],
        )

        # Assert — first reference used
        input_args = mock_replicate.run.call_args.kwargs["input"]
        assert "image" in input_args

    @patch("storyboard_gen.providers.replicate.replicate")
    def test_warns_when_multiple_references_truncated(
        self, mock_replicate, tmp_path, caplog
    ):
        """A warning should be logged when only the first reference is used."""
        # Arrange
        ref1 = tmp_path / "ref1.png"
        ref2 = tmp_path / "ref2.png"
        ref1.write_bytes(b"fake-image-1")
        ref2.write_bytes(b"fake-image-2")

        mock_file = MagicMock()
        mock_file.read.return_value = b"png-bytes"
        mock_replicate.run.return_value = [mock_file]
        provider = ReplicateProvider(model="black-forest-labs/flux-dev")

        import logging

        with caplog.at_level(logging.WARNING):
            # Act
            provider.generate_still(
                prompt="A hero and sidekick",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
                reference_images=[ref1, ref2],
            )

        # Assert — warning logged about truncation
        assert any(
            "only supports 1 reference" in r.message.lower() for r in caplog.records
        )


class TestReplicateGenerateClip:
    def test_raises_not_implemented(self, tmp_path):
        provider = ReplicateProvider(model="black-forest-labs/flux-1.1-pro")

        with pytest.raises(NotImplementedError, match="does not support video"):
            provider.generate_clip(
                prompt="Action",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

    def test_raises_not_implemented_with_new_kwargs(self, tmp_path):
        """New Veo kwargs should not break the NotImplementedError path."""
        from pathlib import Path

        provider = ReplicateProvider(model="black-forest-labs/flux-1.1-pro")

        with pytest.raises(NotImplementedError, match="does not support video"):
            provider.generate_clip(
                prompt="Action",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                source_frame=Path("frame.png"),
                last_frame=Path("last.png"),
                extend_from_video=Path("clip.mp4"),
                seed=42,
                number_of_videos=2,
            )
