# ABOUTME: Tests for the model registry module.
# ABOUTME: Verifies backend listing and model lookup for GUI dropdowns.

from storyboard_gen.model_registry import (
    BACKEND_MODELS,
    get_backends,
    get_models_for_backend,
)


class TestGetBackends:
    """Tests for get_backends()."""

    def test_returns_list(self):
        """get_backends should return a list."""
        result = get_backends()
        assert isinstance(result, list)

    def test_contains_google(self):
        """google should be a known backend."""
        assert "google" in get_backends()

    def test_contains_fal(self):
        """fal should be a known backend."""
        assert "fal" in get_backends()

    def test_contains_replicate(self):
        """replicate should be a known backend."""
        assert "replicate" in get_backends()

    def test_matches_backend_models_keys(self):
        """get_backends should return exactly the BACKEND_MODELS keys."""
        assert get_backends() == list(BACKEND_MODELS.keys())


class TestGetModelsForBackend:
    """Tests for get_models_for_backend()."""

    def test_google_returns_models(self):
        """google backend should have at least one model."""
        models = get_models_for_backend("google")
        assert len(models) > 0

    def test_fal_returns_models(self):
        """fal backend should have at least one model."""
        models = get_models_for_backend("fal")
        assert len(models) > 0

    def test_replicate_returns_models(self):
        """replicate backend should have at least one model."""
        models = get_models_for_backend("replicate")
        assert len(models) > 0

    def test_unknown_backend_returns_empty(self):
        """Unknown backend should return empty list."""
        assert get_models_for_backend("nonexistent") == []

    def test_returns_list_type(self):
        """Return type should be a list of strings."""
        models = get_models_for_backend("google")
        assert isinstance(models, list)
        assert all(isinstance(m, str) for m in models)
