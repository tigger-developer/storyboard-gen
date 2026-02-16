# ABOUTME: Tests for the Google Vertex AI provider implementation.
# ABOUTME: Mocks Google GenAI client calls (external HTTP API — acceptable per TESTING.md).

from unittest.mock import MagicMock, patch

import pytest

from storyboard_gen.providers.google import (
    GoogleProvider,
    IMAGEN_CAPABILITY_MODEL,
)
from storyboard_gen.operation_log import read_operations


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
    operation.error = None
    operation.response = None  # direct return uses .result, not .response
    if video_bytes_list:
        operation.result.generated_videos = mock_videos
    else:
        operation.result.generated_videos = []
    operation.result.rai_media_filtered_count = None
    operation.result.rai_media_filtered_reasons = None
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
        with pytest.raises(RuntimeError, match="safety filter"):
            provider.generate_clip(
                prompt="Fail",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                client=client,
            )

    def test_clip_rai_filter_surfaces_reasons(self, tmp_path):
        """RAI filter reasons should appear in the error message."""
        # Arrange
        client = _make_mock_video_client(video_bytes_list=[])
        op = client.models.generate_videos.return_value
        op.result.rai_media_filtered_count = 1
        op.result.rai_media_filtered_reasons = ["BLOCKED_REASON_SAFETY"]
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act & Assert
        with pytest.raises(RuntimeError, match="BLOCKED_REASON_SAFETY"):
            provider.generate_clip(
                prompt="Filtered",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                client=client,
            )

    def test_clip_operation_error_surfaces_message(self, tmp_path):
        """Operation-level errors should be raised with details."""
        # Arrange
        client = _make_mock_video_client()
        op = client.models.generate_videos.return_value
        op.error = {"code": 400, "message": "Invalid request"}
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act & Assert
        with pytest.raises(RuntimeError, match="Invalid request"):
            provider.generate_clip(
                prompt="Error test",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                client=client,
            )


class TestClipPollingRefresh:
    """Tests for operation polling — issue #30 bug 1."""

    @patch("storyboard_gen.providers.google.time.sleep")
    def test_clip_refreshes_operation_during_polling(self, mock_sleep, tmp_path):
        """operation must be refreshed via client.operations.get() each poll cycle."""
        # Arrange — operation starts not-done, becomes done after one refresh
        client = MagicMock()

        initial_op = MagicMock()
        initial_op.done = False

        refreshed_op = MagicMock()
        refreshed_op.done = True
        refreshed_op.error = None
        refreshed_op.result = None  # polled ops use .response, not .result
        mock_video = MagicMock()
        mock_video.video.video_bytes = b"video-bytes"
        mock_video.video.uri = None
        refreshed_op.response.generated_videos = [mock_video]

        client.models.generate_videos.return_value = initial_op
        client.operations.get.return_value = refreshed_op

        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        result = provider.generate_clip(
            prompt="Polling test",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            client=client,
            poll_interval=10,
        )

        # Assert — operations.get was called to refresh the operation
        client.operations.get.assert_called_once_with(initial_op)
        assert result == [b"video-bytes"]

    @patch("storyboard_gen.providers.google.time.sleep")
    def test_clip_times_out_when_operation_never_completes(self, mock_sleep, tmp_path):
        """RuntimeError when operation stays not-done past max_wait."""
        # Arrange — operations.get always returns not-done
        client = MagicMock()

        never_done = MagicMock()
        never_done.done = False

        client.models.generate_videos.return_value = never_done
        client.operations.get.return_value = never_done

        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act & Assert
        with pytest.raises(RuntimeError, match="timed out"):
            provider.generate_clip(
                prompt="Timeout test",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                client=client,
                poll_interval=10,
                max_wait=10,
            )


class TestClipOutputGcsUri:
    """Tests for output_gcs_uri — issue #30 bug 2."""

    def test_clip_passes_output_gcs_uri(self, tmp_path):
        """When _gcs_bucket is set, output_gcs_uri should appear in config."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")
        provider._gcs_bucket = "gs://my-bucket/output/"

        # Act
        provider.generate_clip(
            prompt="GCS test",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert config.output_gcs_uri == "gs://my-bucket/output/"

    def test_clip_no_output_gcs_uri_when_bucket_not_set(self, tmp_path):
        """When _gcs_bucket is None, output_gcs_uri should not be set."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")
        provider._gcs_bucket = None

        # Act
        provider.generate_clip(
            prompt="No GCS test",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert not hasattr(config, "output_gcs_uri") or config.output_gcs_uri is None

    def test_clip_downloads_from_gcs_uri(self, tmp_path):
        """When video has uri but no bytes, download from GCS."""
        # Arrange
        client = MagicMock()
        mock_video = MagicMock()
        mock_video.video.video_bytes = None
        mock_video.video.uri = "gs://bucket/output/video.mp4"

        operation = MagicMock()
        operation.done = True
        operation.error = None
        operation.response = None  # direct return path
        operation.result.generated_videos = [mock_video]
        client.models.generate_videos.return_value = operation

        provider = GoogleProvider(model="veo-3.1-fast-generate-001")
        provider._gcs_bucket = "gs://bucket/output/"

        output = tmp_path / "scene_01.mp4"

        # Act — patch _download_gcs to write fake bytes instead of calling gsutil
        with patch("storyboard_gen.providers.google._download_gcs") as mock_dl:
            mock_dl.side_effect = lambda uri, dest: dest.write_bytes(b"gcs-video")
            result = provider.generate_clip(
                prompt="GCS download",
                output_path=output,
                aspect_ratio="9:16",
                duration=5,
                client=client,
            )

        # Assert
        mock_dl.assert_called_once_with("gs://bucket/output/video.mp4", output)
        assert result == [b"gcs-video"]


class TestClipDurationSeconds:
    """Tests for duration_seconds — issue #30 bug 3."""

    def test_clip_passes_duration_seconds(self, tmp_path):
        """duration_seconds should be set in GenerateVideosConfig."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Duration test",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=7,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert config.duration_seconds == 7

    def test_clip_clamps_duration_minimum(self, tmp_path):
        """Duration below 5 should be clamped to 5."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Short clip",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=2,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert config.duration_seconds == 5

    def test_clip_clamps_duration_maximum(self, tmp_path):
        """Duration above 8 should be clamped to 8."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Long clip",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=15,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert config.duration_seconds == 8

    def test_clip_duration_float_truncated_to_int(self, tmp_path):
        """Float duration should be truncated to int before clamping."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Float duration",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=6.7,
            client=client,
        )

        # Assert
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert config.duration_seconds == 6


class TestStillRefTruncation:
    """Tests for #31 — truncate still refs to Imagen max (4)."""

    def test_still_truncates_refs_to_max_four(self, tmp_path):
        """More than 4 refs should be truncated to 4 for edit_image."""
        # Arrange — create 6 reference images
        refs = []
        for i in range(6):
            p = tmp_path / f"ref_{i}.png"
            p.write_bytes(b"fake-image")
            refs.append(p)
        client = _make_mock_client()
        provider = GoogleProvider(model="imagen-4.0-generate-001")

        # Act
        provider.generate_still(
            prompt="Crowded scene",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=refs,
            client=client,
        )

        # Assert — only 4 references passed to edit_image
        call_kwargs = client.models.edit_image.call_args.kwargs
        assert len(call_kwargs["reference_images"]) == 4

    def test_still_four_or_fewer_refs_not_truncated(self, tmp_path):
        """Exactly 4 refs should all be passed through."""
        # Arrange
        refs = []
        for i in range(4):
            p = tmp_path / f"ref_{i}.png"
            p.write_bytes(b"fake-image")
            refs.append(p)
        client = _make_mock_client()
        provider = GoogleProvider(model="imagen-4.0-generate-001")

        # Act
        provider.generate_still(
            prompt="Full cast",
            output_path=tmp_path / "scene_01.png",
            aspect_ratio="9:16",
            reference_images=refs,
            client=client,
        )

        # Assert — all 4 passed
        call_kwargs = client.models.edit_image.call_args.kwargs
        assert len(call_kwargs["reference_images"]) == 4


class TestClipRefTruncation:
    """Tests for #31 — truncate clip refs to Veo max (3)."""

    def test_clip_truncates_refs_to_max_three(self, tmp_path):
        """More than 3 refs should be truncated to 3 for generate_videos."""
        # Arrange — create 5 reference images
        refs = []
        for i in range(5):
            p = tmp_path / f"ref_{i}.png"
            p.write_bytes(b"fake-image")
            refs.append(p)
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Crowded clip",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            reference_images=refs,
            client=client,
        )

        # Assert — only 3 references in config
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert len(config.reference_images) == 3

    def test_clip_three_or_fewer_refs_not_truncated(self, tmp_path):
        """Exactly 3 refs should all be passed through."""
        # Arrange
        refs = []
        for i in range(3):
            p = tmp_path / f"ref_{i}.png"
            p.write_bytes(b"fake-image")
            refs.append(p)
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Full cast clip",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            reference_images=refs,
            client=client,
        )

        # Assert — all 3 passed
        call_kwargs = client.models.generate_videos.call_args.kwargs
        config = call_kwargs["config"]
        assert len(config.reference_images) == 3


class TestClipOperationLog:
    """Tests for #33 — operation log entries during clip generation."""

    def test_clip_logs_submitted_and_completed(self, tmp_path):
        """Successful generation should log 'submitted' and 'completed' entries."""
        # Arrange
        client = _make_mock_video_client()
        client.models.generate_videos.return_value.name = "operations/test123"
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="Log test",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            client=client,
            project_dir=tmp_path,
            scene_number="1",
        )

        # Assert
        entries = read_operations(tmp_path)
        assert len(entries) == 2
        assert entries[0]["status"] == "submitted"
        assert entries[0]["operation_id"] == "operations/test123"
        assert entries[0]["scene"] == "1"
        assert entries[0]["provider"] == "google"
        assert entries[1]["status"] == "completed"
        assert entries[1]["operation_id"] == "operations/test123"

    @patch("storyboard_gen.providers.google.time.sleep")
    def test_clip_logs_timed_out(self, mock_sleep, tmp_path):
        """Timeout should log 'submitted' and 'timed_out' entries."""
        # Arrange
        client = MagicMock()
        never_done = MagicMock()
        never_done.done = False
        never_done.name = "operations/timeout456"
        client.models.generate_videos.return_value = never_done
        client.operations.get.return_value = never_done
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act & Assert
        with pytest.raises(RuntimeError, match="timed out"):
            provider.generate_clip(
                prompt="Timeout log test",
                output_path=tmp_path / "scene_01.mp4",
                aspect_ratio="9:16",
                duration=5,
                client=client,
                poll_interval=10,
                max_wait=10,
                project_dir=tmp_path,
                scene_number="2",
            )

        entries = read_operations(tmp_path)
        assert len(entries) == 2
        assert entries[0]["status"] == "submitted"
        assert entries[1]["status"] == "timed_out"

    def test_clip_no_log_when_project_dir_not_set(self, tmp_path):
        """When project_dir is not passed, no log should be written."""
        # Arrange
        client = _make_mock_video_client()
        provider = GoogleProvider(model="veo-3.1-fast-generate-001")

        # Act
        provider.generate_clip(
            prompt="No log test",
            output_path=tmp_path / "scene_01.mp4",
            aspect_ratio="9:16",
            duration=5,
            client=client,
        )

        # Assert — no logs directory created
        assert not (tmp_path / "logs").exists()
