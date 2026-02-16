# ABOUTME: Tests for the Google Vertex AI provider implementation.
# ABOUTME: Mocks Google GenAI client calls (external HTTP API — acceptable per TESTING.md).

from unittest.mock import MagicMock

import pytest

from storyboard_gen.providers.google import (
    GoogleProvider,
    IMAGEN_CAPABILITY_MODEL,
)


def _make_mock_client(image_bytes: bytes = b"png-bytes"):
    """Create a mock Google GenAI client that returns image bytes."""
    client = MagicMock()
    mock_image = MagicMock()
    mock_image.image.image_bytes = image_bytes
    client.models.edit_image.return_value = MagicMock(generated_images=[mock_image])
    client.models.generate_images.return_value = MagicMock(
        generated_images=[mock_image]
    )
    return client


def _make_mock_video_client(video_bytes_list: list[bytes] | None = None):
    """Create a mock Google GenAI client that returns video bytes from Veo.

    Args:
        video_bytes_list: List of bytes for each generated video.
            Defaults to a single video with b"video-bytes".
    """
    if video_bytes_list is None:
        video_bytes_list = [b"video-bytes"]

    client = MagicMock()
    mock_videos = []
    for vb in video_bytes_list:
        mock_video = MagicMock()
        mock_video.video.video_bytes = vb
        mock_video.video.uri = None
        mock_videos.append(mock_video)

    operation = MagicMock()
    operation.done = True
    if video_bytes_list:
        operation.result.generated_videos = mock_videos
    else:
        operation.result.generated_videos = []
    client.models.generate_videos.return_value = operation
    return client


class TestGoogleSingleReference:
    """Regression tests — single reference must continue to work."""

    def test_single_reference_uses_edit_image(self, tmp_path):
        """A single reference image should trigger edit_image with SubjectReferenceImage."""
        # Arrange
        ref = tmp_path / "ref.png"
        ref.write_bytes(b"fake-image")
        client = _make_mock_client()
        provider = GoogleProvider(model="imagen-4.0-generate-001")

        # Act
        provider.generate_still(
            prompt="A hero",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=[ref],
            client=client,
        )

        # Assert — edit_image called, not generate_images
        client.models.edit_image.assert_called_once()
        client.models.generate_images.assert_not_called()
        call_kwargs = client.models.edit_image.call_args.kwargs
        assert call_kwargs["model"] == IMAGEN_CAPABILITY_MODEL
        refs = call_kwargs["reference_images"]
        assert len(refs) == 1

    def test_no_references_uses_generate_images(self, tmp_path):
        """No reference images should use generate_images."""
        # Arrange
        client = _make_mock_client()
        provider = GoogleProvider(model="imagen-4.0-generate-001")

        # Act
        provider.generate_still(
            prompt="A landscape",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            client=client,
        )

        # Assert — generate_images called, not edit_image
        client.models.generate_images.assert_called_once()
        client.models.edit_image.assert_not_called()


class TestGoogleMultiReference:
    """Tests for multi-reference support in Google provider."""

    def test_multiple_references_uses_edit_image(self, tmp_path):
        """Multiple reference images should trigger edit_image, not be discarded."""
        # Arrange
        ref1 = tmp_path / "ref1.png"
        ref2 = tmp_path / "ref2.png"
        ref1.write_bytes(b"fake-image-1")
        ref2.write_bytes(b"fake-image-2")
        client = _make_mock_client()
        provider = GoogleProvider(model="imagen-4.0-generate-001")

        # Act
        provider.generate_still(
            prompt="A hero and sidekick",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=[ref1, ref2],
            client=client,
        )

        # Assert — edit_image called with multiple references
        client.models.edit_image.assert_called_once()
        client.models.generate_images.assert_not_called()
        call_kwargs = client.models.edit_image.call_args.kwargs
        refs = call_kwargs["reference_images"]
        assert len(refs) == 2

    def test_multiple_references_have_distinct_reference_ids(self, tmp_path):
        """Each reference image should get a unique reference_id."""
        # Arrange
        ref1 = tmp_path / "ref1.png"
        ref2 = tmp_path / "ref2.png"
        ref1.write_bytes(b"fake-image-1")
        ref2.write_bytes(b"fake-image-2")
        client = _make_mock_client()
        provider = GoogleProvider(model="imagen-4.0-generate-001")

        # Act
        provider.generate_still(
            prompt="A hero and sidekick",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=[ref1, ref2],
            client=client,
        )

        # Assert — each ref has a distinct reference_id
        call_kwargs = client.models.edit_image.call_args.kwargs
        refs = call_kwargs["reference_images"]
        ref_ids = [r.reference_id for r in refs]
        assert ref_ids == [1, 2]

    def test_multiple_references_skips_nonexistent_files(self, tmp_path):
        """Non-existent reference files should be skipped, existing ones used."""
        # Arrange
        ref1 = tmp_path / "ref1.png"
        ref1.write_bytes(b"fake-image-1")
        ref2 = tmp_path / "missing.png"  # does not exist
        client = _make_mock_client()
        provider = GoogleProvider(model="imagen-4.0-generate-001")

        # Act
        provider.generate_still(
            prompt="A hero and ghost",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=[ref1, ref2],
            client=client,
        )

        # Assert — only the existing ref is used
        client.models.edit_image.assert_called_once()
        call_kwargs = client.models.edit_image.call_args.kwargs
        refs = call_kwargs["reference_images"]
        assert len(refs) == 1

    def test_all_references_nonexistent_falls_back_to_generate(self, tmp_path):
        """If all reference files are missing, fall back to generate_images."""
        # Arrange
        ref1 = tmp_path / "missing1.png"
        ref2 = tmp_path / "missing2.png"
        client = _make_mock_client()
        provider = GoogleProvider(model="imagen-4.0-generate-001")

        # Act
        provider.generate_still(
            prompt="A hero and sidekick",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=[ref1, ref2],
            client=client,
        )

        # Assert — falls back to generate_images
        client.models.generate_images.assert_called_once()
        client.models.edit_image.assert_not_called()


class TestGoogleClipGeneration:
    """Tests for Veo clip generation with full parameter support."""

    def test_clip_passes_aspect_ratio(self, tmp_path):
        """aspect_ratio should be included in GenerateVideosConfig."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="A boy running",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert config.aspect_ratio == "9:16"

    def test_clip_passes_reference_images_as_wrapped_objects(self, tmp_path):
        """reference_images should be wrapped in VideoGenerationReferenceImage."""
        from google.genai import types

        # Arrange
        ref = tmp_path / "ref.png"
        ref.write_bytes(b"fake-image")
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="A boy running",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            reference_images=[ref],
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert len(config.reference_images) == 1
        ref_img = config.reference_images[0]
        assert isinstance(ref_img, types.VideoGenerationReferenceImage)
        assert ref_img.reference_type == "ASSET"

    def test_clip_skips_references_when_source_frame_set(self, tmp_path):
        """reference_images should be omitted when source_frame is provided."""
        # Arrange
        ref = tmp_path / "ref.png"
        ref.write_bytes(b"fake-image")
        frame = tmp_path / "frame.png"
        frame.write_bytes(b"fake-frame")
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Animate with ref",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            reference_images=[ref],
            source_frame=frame,
            client=client,
        )

        # Assert — reference_images not set, image kwarg IS set
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert not config.reference_images
        assert call_kwargs["image"] is not None

    def test_clip_skips_references_when_extend_from_video_set(self, tmp_path):
        """reference_images should be omitted when extend_from_video is provided."""
        # Arrange
        ref = tmp_path / "ref.png"
        ref.write_bytes(b"fake-image")
        video = tmp_path / "prev.mp4"
        video.write_bytes(b"fake-video")
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Extend with ref",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            reference_images=[ref],
            extend_from_video=video,
            client=client,
        )

        # Assert — reference_images not set, video kwarg IS set
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert not config.reference_images
        assert call_kwargs["video"] is not None

    def test_clip_skips_nonexistent_references(self, tmp_path):
        """Non-existent reference files should be skipped."""
        # Arrange
        missing = tmp_path / "missing.png"
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="A boy running",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            reference_images=[missing],
            client=client,
        )

        # Assert — no reference_images in config (or empty list)
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert not config.reference_images

    def test_clip_passes_source_frame_as_image(self, tmp_path):
        """source_frame should be passed as image= kwarg."""
        # Arrange
        frame = tmp_path / "frame.png"
        frame.write_bytes(b"fake-frame")
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Animate this",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            source_frame=frame,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        assert call_kwargs["image"] is not None

    def test_clip_passes_last_frame_in_config(self, tmp_path):
        """last_frame should be passed in GenerateVideosConfig."""
        # Arrange
        frame = tmp_path / "first.png"
        frame.write_bytes(b"fake-first")
        last = tmp_path / "last.png"
        last.write_bytes(b"fake-last")
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Interpolate",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            source_frame=frame,
            last_frame=last,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert config.last_frame is not None

    def test_clip_passes_extend_from_video(self, tmp_path):
        """extend_from_video should be passed as video= kwarg."""
        # Arrange
        video = tmp_path / "prev_clip.mp4"
        video.write_bytes(b"fake-video")
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Continue scene",
            output_path=tmp_path / "scene_02.mp4",
            aspect_ratio="9:16",
            duration=5,
            extend_from_video=video,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        assert call_kwargs["video"] is not None

    def test_clip_passes_seed_in_config(self, tmp_path):
        """seed should be passed in GenerateVideosConfig."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Deterministic",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            seed=42,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert config.seed == 42

    def test_clip_passes_number_of_videos_in_config(self, tmp_path):
        """number_of_videos should be passed in GenerateVideosConfig."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Multi-take",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            number_of_videos=3,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert config.number_of_videos == 3

    def test_clip_returns_list_of_bytes(self, tmp_path):
        """generate_clip should return a list of video bytes."""
        # Arrange
        client = _make_mock_video_client(video_bytes_list=[b"video-1", b"video-2"])
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        result = provider.generate_clip(
            prompt="Multi-take",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            number_of_videos=2,
            client=client,
        )

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == b"video-1"
        assert result[1] == b"video-2"

    def test_clip_no_video_generated_raises(self, tmp_path):
        """RuntimeError when no videos are generated."""
        # Arrange
        client = _make_mock_video_client(video_bytes_list=[])
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act & Assert
        with pytest.raises(RuntimeError, match="No video generated"):
            provider.generate_clip(
                prompt="Fail",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                client=client,
            )
