# ABOUTME: Tests for provider registry, factory, and implementations.
# ABOUTME: Mocks external API calls (acceptable per TESTING.md).

import pytest

from storyboard_gen.providers import create_provider
from storyboard_gen.providers.base import ImageProvider


class TestProviderFactory:
    def test_create_provider_unknown_backend_raises(self):
        # Act & Assert
        with pytest.raises(ValueError, match="Unknown provider backend"):
            create_provider("midjourney", "v6")

    def test_create_provider_google_returns_image_provider(self):
        # Act
        provider = create_provider("google", "imagen-4.0-generate-001")

        # Assert
        assert isinstance(provider, ImageProvider)

    def test_create_provider_passes_model_and_options(self):
        # Act
        provider = create_provider(
            "google", "imagen-4.0-generate-001", {"number_of_images": 2}
        )

        # Assert
        assert provider.model == "imagen-4.0-generate-001"
        assert provider.options == {"number_of_images": 2}

    def test_create_provider_fal_returns_image_provider(self):
        # Act
        provider = create_provider("fal", "fal-ai/flux-pro/v1.1")

        # Assert
        assert isinstance(provider, ImageProvider)
        assert provider.model == "fal-ai/flux-pro/v1.1"

    def test_create_provider_replicate_returns_image_provider(self):
        # Act
        provider = create_provider("replicate", "black-forest-labs/flux-1.1-pro")

        # Assert
        assert isinstance(provider, ImageProvider)
        assert provider.model == "black-forest-labs/flux-1.1-pro"
