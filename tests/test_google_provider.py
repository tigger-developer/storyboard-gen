# ABOUTME: Tests for the Google Vertex AI provider implementation.
# ABOUTME: Mocks Google GenAI client calls (external HTTP API — acceptable per TESTING.md).

from unittest.mock import MagicMock

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
