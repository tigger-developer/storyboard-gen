# ABOUTME: Tests for the FAL.ai provider implementation.
# ABOUTME: Mocks fal_client calls (external HTTP API — acceptable per TESTING.md).

import hashlib
import json
from unittest.mock import patch

import pytest

from storyboard_gen.models import Character
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
    """Tests for FAL clip generation via Kling models (#34)."""

    def test_non_video_model_raises_not_implemented(self, tmp_path):
        """Flux/Kontext still models should still raise NotImplementedError."""
        provider = FalProvider(model="fal-ai/flux-pro/v1.1")

        with pytest.raises(NotImplementedError, match="does not support video"):
            provider.generate_clip(
                prompt="Action",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_calls_subscribe_with_correct_arguments(self, mock_fal, tmp_path):
        """Text-to-video should call subscribe with prompt, duration, aspect_ratio."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/text-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            result = provider.generate_clip(
                prompt="A boy running",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

        # Assert
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/kling-video/v2.1/pro/text-to-video"
        arguments = call_args.kwargs["arguments"]
        assert arguments["prompt"] == "A boy running"
        assert arguments["duration"] == "5"
        assert arguments["aspect_ratio"] == "9:16"
        assert result == [b"video-bytes"]

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_uploads_source_frame(self, mock_fal, tmp_path):
        """source_frame should be uploaded to CDN and passed as image_url."""
        # Arrange
        frame = tmp_path / "frame.png"
        frame.write_bytes(b"fake-frame")
        mock_fal.upload_file.return_value = "https://fal.media/files/frame.png"
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="Animate this",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                source_frame=frame,
            )

        # Assert
        mock_fal.upload_file.assert_called_once_with(str(frame))
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["image_url"] == "https://fal.media/files/frame.png"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_v3_uses_start_image_url(self, mock_fal, tmp_path):
        """v3 models should use start_image_url instead of image_url."""
        # Arrange
        frame = tmp_path / "frame.png"
        frame.write_bytes(b"fake-frame")
        mock_fal.upload_file.return_value = "https://fal.media/files/frame.png"
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="Animate this",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                source_frame=frame,
            )

        # Assert
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["start_image_url"] == "https://fal.media/files/frame.png"
        assert "image_url" not in arguments

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_passes_last_frame_v2(self, mock_fal, tmp_path):
        """last_frame should map to tail_image_url for v2.x models."""
        # Arrange
        frame = tmp_path / "frame.png"
        frame.write_bytes(b"fake-frame")
        last = tmp_path / "last.png"
        last.write_bytes(b"fake-last")
        mock_fal.upload_file.side_effect = [
            "https://fal.media/files/frame.png",
            "https://fal.media/files/last.png",
        ]
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="Interpolate",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                source_frame=frame,
                last_frame=last,
            )

        # Assert
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["tail_image_url"] == "https://fal.media/files/last.png"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_passes_last_frame_v3(self, mock_fal, tmp_path):
        """last_frame should map to end_image_url for v3 models."""
        # Arrange
        frame = tmp_path / "frame.png"
        frame.write_bytes(b"fake-frame")
        last = tmp_path / "last.png"
        last.write_bytes(b"fake-last")
        mock_fal.upload_file.side_effect = [
            "https://fal.media/files/frame.png",
            "https://fal.media/files/last.png",
        ]
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="Interpolate",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                source_frame=frame,
                last_frame=last,
            )

        # Assert
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["end_image_url"] == "https://fal.media/files/last.png"
        assert "tail_image_url" not in arguments

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_passes_options(self, mock_fal, tmp_path):
        """Provider options should be merged into arguments."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(
            model="fal-ai/kling-video/v2.1/pro/image-to-video",
            options={"cfg_scale": 0.7, "negative_prompt": "blur"},
        )

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="Action",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="16:9",
                duration=10,
            )

        # Assert
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["cfg_scale"] == 0.7
        assert arguments["negative_prompt"] == "blur"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_duration_passed_as_string(self, mock_fal, tmp_path):
        """Duration should be converted to string for FAL API."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="Test",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=10.5,
            )

        # Assert — float truncated to int, passed as string
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["duration"] == "10"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_no_video_raises(self, mock_fal, tmp_path):
        """RuntimeError when no video is returned."""
        # Arrange
        mock_fal.subscribe.return_value = {"video": None}
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/image-to-video")

        # Act & Assert
        with pytest.raises(RuntimeError, match="No video generated"):
            provider.generate_clip(
                prompt="Fail",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_api_error_surfaces(self, mock_fal, tmp_path):
        """FAL API errors should be wrapped in RuntimeError."""
        # Arrange
        mock_fal.subscribe.side_effect = Exception("quota exceeded")
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/image-to-video")

        # Act & Assert
        with pytest.raises(RuntimeError, match="FAL API error"):
            provider.generate_clip(
                prompt="Error test",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_defaults_generate_audio_false(self, mock_fal, tmp_path):
        """generate_audio should default to False (#35)."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="A boy running",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

        # Assert
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["generate_audio"] is False

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_generate_audio_overridable_via_options(self, mock_fal, tmp_path):
        """User can override generate_audio to True via options (#35)."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(
            model="fal-ai/kling-video/v2.1/pro/image-to-video",
            options={"generate_audio": True},
        )

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="A boy running",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

        # Assert — options override the default
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["generate_audio"] is True

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_swaps_i2v_to_t2v_when_no_source_frame(self, mock_fal, tmp_path):
        """image-to-video endpoint should swap to text-to-video when no source_frame (#36)."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act — no source_frame
            provider.generate_clip(
                prompt="A boy running",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

        # Assert — endpoint swapped to text-to-video
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/kling-video/v2.1/pro/text-to-video"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_swaps_t2v_to_i2v_when_source_frame_set(self, mock_fal, tmp_path):
        """text-to-video endpoint should swap to image-to-video when source_frame is set (#36)."""
        # Arrange
        frame = tmp_path / "frame.png"
        frame.write_bytes(b"fake-frame")
        mock_fal.upload_file.return_value = "https://fal.media/files/frame.png"
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/text-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act — source_frame provided
            provider.generate_clip(
                prompt="Animate this",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                source_frame=frame,
            )

        # Assert — endpoint swapped to image-to-video
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/kling-video/v2.1/pro/image-to-video"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_no_swap_i2v_with_source_frame(self, mock_fal, tmp_path):
        """image-to-video with source_frame should not swap (#36)."""
        # Arrange
        frame = tmp_path / "frame.png"
        frame.write_bytes(b"fake-frame")
        mock_fal.upload_file.return_value = "https://fal.media/files/frame.png"
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="Animate this",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                source_frame=frame,
            )

        # Assert — no swap, stays as image-to-video
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/kling-video/v2.1/pro/image-to-video"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_no_swap_t2v_without_source_frame(self, mock_fal, tmp_path):
        """text-to-video without source_frame should not swap (#36)."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/text-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="A boy running",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

        # Assert — no swap, stays as text-to-video
        call_args = mock_fal.subscribe.call_args
        assert call_args.args[0] == "fal-ai/kling-video/v2.1/pro/text-to-video"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_clip_endpoint_swap_logged(self, mock_fal, tmp_path, caplog):
        """Endpoint swap should be logged at INFO level (#36)."""
        import logging

        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/image-to-video")

        with (
            caplog.at_level(logging.INFO),
            patch("storyboard_gen.providers.fal._download_url") as mock_dl,
        ):
            mock_dl.return_value = b"video-bytes"

            # Act — no source_frame triggers swap
            provider.generate_clip(
                prompt="A boy running",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

        # Assert — swap logged
        assert any("text-to-video" in r.message for r in caplog.records)


class TestFalO3Detection:
    """Tests for O3 model detection (#37)."""

    def test_is_o3_positive_standard(self):
        """O3 standard model should be detected."""
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")
        assert provider._is_o3 is True

    def test_is_o3_positive_pro(self):
        """O3 pro model should be detected."""
        provider = FalProvider(model="fal-ai/kling-video/o3/pro/text-to-video")
        assert provider._is_o3 is True

    def test_is_o3_case_insensitive(self):
        """O3 detection should be case-insensitive."""
        provider = FalProvider(model="fal-ai/kling-video/O3/standard/image-to-video")
        assert provider._is_o3 is True

    def test_is_o3_negative_v2(self):
        """v2.1 models are not O3."""
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/text-to-video")
        assert provider._is_o3 is False

    def test_is_o3_negative_v3(self):
        """v3 models are not O3."""
        provider = FalProvider(model="fal-ai/kling-video/v3/standard/image-to-video")
        assert provider._is_o3 is False

    def test_is_o3_negative_flux(self):
        """Flux models are not O3."""
        provider = FalProvider(model="fal-ai/flux-pro/v1.1")
        assert provider._is_o3 is False


class TestFalO3PromptRewrite:
    """Tests for O3 @character_id → @ElementN prompt rewriting (#37)."""

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_o3_rewrites_at_char_to_at_element(self, mock_fal, tmp_path):
        """@boy → @Element1, @mum → @Element2 in prompt."""
        # Arrange
        ref_boy = tmp_path / "boy.jpg"
        ref_mum = tmp_path / "mum.jpg"
        ref_boy.write_bytes(b"boy-image")
        ref_mum.write_bytes(b"mum-image")

        mock_fal.upload_file.side_effect = [
            "https://fal.media/files/boy.png",
            "https://fal.media/files/mum.png",
        ]
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [
            Character(
                id="boy", description="A boy with curly hair", reference=[ref_boy]
            ),
            Character(
                id="mum", description="A woman with dark hair", reference=[ref_mum]
            ),
        ]
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@boy runs toward @mum at the door.",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
            )

        # Assert — prompt rewritten with @ElementN
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["prompt"] == "@Element1 runs toward @Element2 at the door."

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_o3_auto_prepends_when_no_at_tokens(self, mock_fal, tmp_path):
        """When no @character_id tokens in prompt, auto-prepend descriptions."""
        # Arrange
        ref = tmp_path / "boy.jpg"
        ref.write_bytes(b"boy-image")

        mock_fal.upload_file.return_value = "https://fal.media/files/boy.png"
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [
            Character(id="boy", description="A boy with curly hair", reference=[ref]),
        ]
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="A child waves hello.",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
            )

        # Assert — @Element1 description prepended
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        prompt = arguments["prompt"]
        assert prompt.startswith("@Element1 is A boy with curly hair.")
        assert "A child waves hello." in prompt

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_o3_rewrite_case_insensitive(self, mock_fal, tmp_path):
        """@Boy and @BOY should both be rewritten to @Element1."""
        # Arrange
        ref = tmp_path / "boy.jpg"
        ref.write_bytes(b"boy-image")

        mock_fal.upload_file.return_value = "https://fal.media/files/boy.png"
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [
            Character(id="boy", description="A boy", reference=[ref]),
        ]
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@Boy waves at @BOY in the mirror.",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
            )

        # Assert — both replaced
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["prompt"] == "@Element1 waves at @Element1 in the mirror."


class TestFalO3Elements:
    """Tests for O3 elements array building (#37)."""

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_o3_builds_elements_from_characters(self, mock_fal, tmp_path):
        """Character with 2 refs → frontal_image_url + reference_image_urls."""
        # Arrange
        ref1 = tmp_path / "boy_front.jpg"
        ref2 = tmp_path / "boy_side.jpg"
        ref1.write_bytes(b"front-image")
        ref2.write_bytes(b"side-image")

        mock_fal.upload_file.side_effect = [
            "https://fal.media/files/front.png",
            "https://fal.media/files/side.png",
        ]
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [
            Character(id="boy", description="A boy", reference=[ref1, ref2]),
        ]
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@boy waves",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
            )

        # Assert — elements array with frontal + additional refs
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        elements = arguments["elements"]
        assert len(elements) == 1
        assert elements[0]["frontal_image_url"] == "https://fal.media/files/front.png"
        assert elements[0]["reference_image_urls"] == [
            "https://fal.media/files/side.png"
        ]

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_o3_element_ordering_matches_characters_list(self, mock_fal, tmp_path):
        """Elements order should match the scene's characters list order."""
        # Arrange
        ref_boy = tmp_path / "boy.jpg"
        ref_mum = tmp_path / "mum.jpg"
        ref_boy.write_bytes(b"boy-image")
        ref_mum.write_bytes(b"mum-image")

        mock_fal.upload_file.side_effect = [
            "https://fal.media/files/boy.png",
            "https://fal.media/files/mum.png",
        ]
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [
            Character(id="boy", description="A boy", reference=[ref_boy]),
            Character(id="mum", description="A woman", reference=[ref_mum]),
        ]
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@boy and @mum",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
            )

        # Assert — elements in order: [boy, mum]
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        elements = arguments["elements"]
        assert len(elements) == 2
        assert elements[0]["frontal_image_url"] == "https://fal.media/files/boy.png"
        assert elements[1]["frontal_image_url"] == "https://fal.media/files/mum.png"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_o3_characters_without_refs_skipped_in_elements(self, mock_fal, tmp_path):
        """Characters with no reference images should not generate elements."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [Character(id="boy", description="A boy", reference=[])]
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@boy waves",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
            )

        # Assert — no elements key (character had no refs)
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert "elements" not in arguments

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_non_o3_elements_not_passed(self, mock_fal, tmp_path):
        """Non-O3 models should never receive elements."""
        # Arrange
        ref = tmp_path / "boy.jpg"
        ref.write_bytes(b"boy-image")

        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [Character(id="boy", description="A boy", reference=[ref])]
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/text-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@boy waves",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
            )

        # Assert — no elements for non-O3
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert "elements" not in arguments


class TestFalNonO3AtStrip:
    """Tests for stripping @character_id prefix on non-O3 models (#37)."""

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_non_o3_strips_at_prefix_from_prompt(self, mock_fal, tmp_path):
        """Non-O3 Kling should strip @ prefix from character tokens."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [
            Character(id="boy", description="A boy", reference=[]),
            Character(id="mum", description="A woman", reference=[]),
        ]
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/text-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@boy runs toward @mum",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
            )

        # Assert — @ stripped from character tokens
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["prompt"] == "boy runs toward mum"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_non_o3_at_strip_case_insensitive(self, mock_fal, tmp_path):
        """@ stripping should be case-insensitive."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [Character(id="boy", description="A boy", reference=[])]
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/text-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@Boy runs fast",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
            )

        # Assert
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["prompt"] == "Boy runs fast"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_no_scene_characters_leaves_prompt_unchanged(self, mock_fal, tmp_path):
        """Without scene_characters, @ tokens stay in the prompt."""
        # Arrange
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }
        provider = FalProvider(model="fal-ai/kling-video/v2.1/pro/text-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@someone runs",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
            )

        # Assert — no scene_characters means no rewriting
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert arguments["prompt"] == "@someone runs"


class TestFalCdnCache:
    """Tests for CDN URL caching to avoid re-uploading references (#37)."""

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_cdn_cache_miss_triggers_upload_and_stores(self, mock_fal, tmp_path):
        """Cache miss should upload the file and store the hash → URL mapping."""
        # Arrange
        ref = tmp_path / "boy.jpg"
        ref.write_bytes(b"boy-image-data")

        mock_fal.upload_file.return_value = "https://fal.media/files/boy.png"
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        chars = [Character(id="boy", description="A boy", reference=[ref])]
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@boy waves",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
                project_dir=project_dir,
            )

        # Assert — upload called, cache file created with correct hash
        mock_fal.upload_file.assert_called_once_with(str(ref))
        cache_path = project_dir / "logs" / "cdn_cache.json"
        assert cache_path.exists()
        cache = json.loads(cache_path.read_text())
        file_hash = hashlib.sha256(b"boy-image-data").hexdigest()
        assert cache[file_hash] == "https://fal.media/files/boy.png"

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_cdn_cache_hit_skips_upload(self, mock_fal, tmp_path):
        """Cache hit should reuse the cached URL without uploading."""
        # Arrange
        ref = tmp_path / "boy.jpg"
        ref.write_bytes(b"boy-image-data")
        file_hash = hashlib.sha256(b"boy-image-data").hexdigest()

        project_dir = tmp_path / "project"
        logs_dir = project_dir / "logs"
        logs_dir.mkdir(parents=True)
        cache = {file_hash: "https://fal.media/files/cached_boy.png"}
        (logs_dir / "cdn_cache.json").write_text(json.dumps(cache))

        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [Character(id="boy", description="A boy", reference=[ref])]
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@boy waves",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
                project_dir=project_dir,
            )

        # Assert — no upload (cache hit), cached URL used in elements
        mock_fal.upload_file.assert_not_called()
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert (
            arguments["elements"][0]["frontal_image_url"]
            == "https://fal.media/files/cached_boy.png"
        )

    @patch("storyboard_gen.providers.fal.fal_client")
    def test_cdn_cache_changed_file_triggers_reupload(self, mock_fal, tmp_path):
        """Changed file (different hash) should re-upload and update cache."""
        # Arrange — cache has OLD hash
        ref = tmp_path / "boy.jpg"
        ref.write_bytes(b"new-image-data")
        old_hash = hashlib.sha256(b"old-image-data").hexdigest()

        project_dir = tmp_path / "project"
        logs_dir = project_dir / "logs"
        logs_dir.mkdir(parents=True)
        cache = {old_hash: "https://fal.media/files/old_boy.png"}
        (logs_dir / "cdn_cache.json").write_text(json.dumps(cache))

        mock_fal.upload_file.return_value = "https://fal.media/files/new_boy.png"
        mock_fal.subscribe.return_value = {
            "video": {"url": "https://fal.media/files/video.mp4"},
        }

        chars = [Character(id="boy", description="A boy", reference=[ref])]
        provider = FalProvider(model="fal-ai/kling-video/o3/standard/image-to-video")

        with patch("storyboard_gen.providers.fal._download_url") as mock_dl:
            mock_dl.return_value = b"video-bytes"

            # Act
            provider.generate_clip(
                prompt="@boy waves",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                scene_characters=chars,
                project_dir=project_dir,
            )

        # Assert — re-upload happened, new URL in elements and cache
        mock_fal.upload_file.assert_called_once()
        arguments = mock_fal.subscribe.call_args.kwargs["arguments"]
        assert (
            arguments["elements"][0]["frontal_image_url"]
            == "https://fal.media/files/new_boy.png"
        )
        new_hash = hashlib.sha256(b"new-image-data").hexdigest()
        updated_cache = json.loads((logs_dir / "cdn_cache.json").read_text())
        assert updated_cache[new_hash] == "https://fal.media/files/new_boy.png"
