# ABOUTME: Tests for the FAL.ai provider implementation.
# ABOUTME: Mocks fal_client calls (external HTTP API — acceptable per TESTING.md).

from unittest.mock import patch

import pytest

from storyboard_gen.providers.fal import FalProvider, _map_aspect_ratio


class TestMapAspectRatio:
    def test_map_portrait_9_16(self):
        assert _map_aspect_ratio("9:16") == "portrait_16_9"

    def test_map_landscape_16_9(self):
        assert _map_aspect_ratio("16:9") == "landscape_16_9"

    def test_map_landscape_4_3(self):
        assert _map_aspect_ratio("4:3") == "landscape_4_3"

    def test_map_square_1_1(self):
        assert _map_aspect_ratio("1:1") == "square_hd"

    def test_map_unknown_ratio_raises(self):
        with pytest.raises(ValueError, match="Unsupported aspect ratio"):
            _map_aspect_ratio("3:2")


class TestFalProviderInit:
    def test_stores_model_and_options(self):
        provider = FalProvider(model="fal-ai/flux-pro/v1.1", options={"seed": 42})
        assert provider.model == "fal-ai/flux-pro/v1.1"
        assert provider.options == {"seed": 42}

    def test_defaults_empty_options(self):
        provider = FalProvider(model="fal-ai/flux-pro/v1.1")
        assert provider.options == {}


class TestFalGenerateStill:
    @patch("storyboard_gen.providers.fal.fal_client")
    def test_calls_subscribe_with_correct_arguments(self, mock_fal, tmp_path):
        # Arrange
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/test.png"}],
        }
        mock_fal.upload_file.return_value = "https://fal.media/files/ref.png"
        provider = FalProvider(model="fal-ai/flux-pro/v1.1")

        # Stub URL download
        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            result = provider.generate_still(
                prompt="A boy in a field",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
            )

        # Assert
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/flux-pro/v1.1"
        arguments = call_args.kwargs["arguments"]
        assert arguments["prompt"] == "A boy in a field"
        assert arguments["image_size"] == "portrait_16_9"
        assert arguments["num_images"] == 1
        assert arguments["output_format"] == "png"
        assert result == b"png-bytes"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_passes_options_as_arguments(self, mock_fal, tmp_path):
        # Arrange
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/test.png"}],
        }
        provider = FalProvider(
            model="fal-ai/flux-pro/v1.1", options={"seed": 42, "safety_tolerance": 5}
        )

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="Prompt",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="16:9",
            )

        # Assert — options merged into arguments
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["seed"] == 42
        assert arguments["safety_tolerance"] == 5

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_uploads_single_reference_image(self, mock_fal, tmp_path):
        # Arrange
        ref_path = tmp_path / "ref.png"
        ref_path.write_bytes(b"fake-image")

        mock_fal.upload_file.return_value = "https://fal.media/files/ref.png"
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(model="fal-ai/flux-general")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="A hero",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
                reference_images=[ref_path],
            )

        # Assert — reference uploaded and passed
        mock_fal.upload_file.assert_called_once_with(str(ref_path))
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["reference_image_url"] == "https://fal.media/files/ref.png"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_skips_nonexistent_reference_image(self, mock_fal, tmp_path):
        # Arrange
        ref_path = tmp_path / "missing.png"  # does not exist

        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(model="fal-ai/flux-general")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="A hero",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
                reference_images=[ref_path],
            )

        # Assert — no upload, no reference in arguments
        mock_fal.upload_file.assert_not_called()
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert "reference_image_url" not in arguments

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_raises_when_no_images_returned(self, mock_fal, tmp_path):
        # Arrange
        mock_fal.subscribe.return_value = {"images": []}
        provider = FalProvider(model="fal-ai/flux-pro/v1.1")

        # Act & Assert
        with pytest.raises(RuntimeError, match="No image generated"):
            provider.generate_still(
                prompt="Prompt",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
            )

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_raises_when_subscribe_raises(self, mock_fal, tmp_path):
        # Arrange
        mock_fal.subscribe.side_effect = Exception("API error")
        provider = FalProvider(model="fal-ai/flux-pro/v1.1")

        # Act & Assert
        with pytest.raises(RuntimeError, match="FAL API error"):
            provider.generate_still(
                prompt="Prompt",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
            )


class TestFalKontextStill:
    """Tests for Kontext model routing (image-to-image and text-to-image)."""

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_kontext_text_to_image_appends_endpoint(self, mock_fal, tmp_path):
        """No references → appends /text-to-image, uses image_size preset."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(model="fal-ai/flux-pro/kontext")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="A boy in a field",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
            )

        # Assert — endpoint has /text-to-image appended
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/flux-pro/kontext/text-to-image"
        arguments = call_args.kwargs["arguments"]
        assert arguments["image_size"] == "portrait_16_9"
        assert "image_url" not in arguments
        assert "aspect_ratio" not in arguments

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_kontext_image_to_image_uses_base_endpoint(self, mock_fal, tmp_path):
        """With reference → base endpoint, image_url, raw aspect_ratio."""
        # Arrange
        ref_path = tmp_path / "ref.png"
        ref_path.write_bytes(b"fake-image")

        mock_fal.upload_file.return_value = "https://fal.media/files/ref.png"
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(model="fal-ai/flux-pro/kontext")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="A boy in a field",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
                reference_images=[ref_path],
            )

        # Assert — base endpoint, image_url set, raw aspect_ratio
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/flux-pro/kontext"
        arguments = call_args.kwargs["arguments"]
        assert arguments["image_url"] == "https://fal.media/files/ref.png"
        assert arguments["aspect_ratio"] == "9:16"
        assert "image_size" not in arguments
        assert "reference_image_url" not in arguments

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_kontext_image_to_image_skips_nonexistent_reference(
        self, mock_fal, tmp_path
    ):
        """Missing ref file → falls back to text-to-image."""
        # Arrange
        ref_path = tmp_path / "missing.png"  # does not exist

        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(model="fal-ai/flux-pro/kontext")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="A boy in a field",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
                reference_images=[ref_path],
            )

        # Assert — falls back to text-to-image
        mock_fal.upload_file.assert_not_called()
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/flux-pro/kontext/text-to-image"
        arguments = call_args.kwargs["arguments"]
        assert "image_url" not in arguments

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_kontext_passes_options(self, mock_fal, tmp_path):
        """Provider options (seed, safety_tolerance) are merged into arguments."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(
            model="fal-ai/flux-pro/kontext",
            options={"seed": 42, "safety_tolerance": 5},
        )

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="Prompt",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="16:9",
            )

        # Assert
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["seed"] == 42
        assert arguments["safety_tolerance"] == 5

    def test_is_kontext_detection(self):
        """_is_kontext returns True for Kontext models, False otherwise."""
        # Positive cases
        assert FalProvider(model="fal-ai/flux-pro/kontext")._is_kontext is True
        assert (
            FalProvider(model="fal-ai/flux-pro/kontext/text-to-image")._is_kontext
            is True
        )
        assert FalProvider(model="fal-ai/Kontext-Model")._is_kontext is True

        # Negative cases
        assert FalProvider(model="fal-ai/flux-pro/v1.1")._is_kontext is False
        assert FalProvider(model="fal-ai/flux-general")._is_kontext is False

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_flux_model_with_reference_uses_reference_image_url(
        self, mock_fal, tmp_path
    ):
        """Regression: Flux models still use reference_image_url, not image_url."""
        # Arrange
        ref_path = tmp_path / "ref.png"
        ref_path.write_bytes(b"fake-image")

        mock_fal.upload_file.return_value = "https://fal.media/files/ref.png"
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(model="fal-ai/flux-general")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="A hero",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
                reference_images=[ref_path],
            )

        # Assert — Flux uses reference_image_url, NOT image_url
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/flux-general"
        arguments = call_args.kwargs["arguments"]
        assert arguments["reference_image_url"] == "https://fal.media/files/ref.png"
        assert "image_url" not in arguments


class TestFalMultiReference:
    """Tests for multi-reference image handling in FAL provider."""

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_flux_uses_first_reference_when_multiple_provided(self, mock_fal, tmp_path):
        """Multi-ref Flux scenes should use the first reference, not discard all."""
        # Arrange
        ref1 = tmp_path / "ref1.png"
        ref2 = tmp_path / "ref2.png"
        ref1.write_bytes(b"fake-image-1")
        ref2.write_bytes(b"fake-image-2")

        mock_fal.upload_file.return_value = "https://fal.media/files/ref1.png"
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(model="fal-ai/flux-general")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="A hero and sidekick",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
                reference_images=[ref1, ref2],
            )

        # Assert — first reference uploaded and used
        mock_fal.upload_file.assert_called_once_with(str(ref1))
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["reference_image_url"] == "https://fal.media/files/ref1.png"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_kontext_uses_first_reference_when_multiple_provided(
        self, mock_fal, tmp_path
    ):
        """Multi-ref Kontext scenes should use the first reference for image-to-image."""
        # Arrange
        ref1 = tmp_path / "ref1.png"
        ref2 = tmp_path / "ref2.png"
        ref1.write_bytes(b"fake-image-1")
        ref2.write_bytes(b"fake-image-2")

        mock_fal.upload_file.return_value = "https://fal.media/files/ref1.png"
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(model="fal-ai/flux-pro/kontext")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"png-bytes"

            # Act
            provider.generate_still(
                prompt="A hero and sidekick",
                output_path=tmp_path / "scene_01.png",
                aspect_ratio="9:16",
                reference_images=[ref1, ref2],
            )

        # Assert — first reference uploaded and used for image-to-image
        mock_fal.upload_file.assert_called_once_with(str(ref1))
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/flux-pro/kontext"
        arguments = call_args.kwargs["arguments"]
        assert arguments["image_url"] == "https://fal.media/files/ref1.png"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_warns_when_multiple_references_truncated(self, mock_fal, tmp_path, caplog):
        """A warning should be logged when only the first reference is used."""
        # Arrange
        ref1 = tmp_path / "ref1.png"
        ref2 = tmp_path / "ref2.png"
        ref1.write_bytes(b"fake-image-1")
        ref2.write_bytes(b"fake-image-2")

        mock_fal.upload_file.return_value = "https://fal.media/files/ref1.png"
        mock_fal.subscribe.return_value = {
            "images": [{"url": "https://fal.media/files/out.png"}],
        }
        provider = FalProvider(model="fal-ai/flux-general")

        import logging

        with (
            caplog.at_level(logging.WARNING),
            patch("storyboard_gen.providers.fal._download_url") as mock_dl,
        ):
            mock_dl.return_value = b"png-bytes"

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


class TestFalGenerateClip:
    def test_raises_not_implemented(self, tmp_path):
        provider = FalProvider(model="fal-ai/flux-pro/v1.1")

        with pytest.raises(NotImplementedError, match="does not support video"):
            provider.generate_clip(
                prompt="Action",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )
