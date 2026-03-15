# ABOUTME: Tests for the model registry module.
# ABOUTME: Verifies backend listing, model lookup, and sync with docs/models.md.

import re
from pathlib import Path

from storyboard_gen.model_registry import (
    BACKEND_MODELS,
    get_all_models,
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


class TestGetAllModels:
    """Tests for get_all_models()."""

    def test_returns_dict(self):
        """get_all_models should return a dict."""
        result = get_all_models()
        assert isinstance(result, dict)

    def test_values_are_backend_names(self):
        """Every value should be a known backend name."""
        backends = set(get_backends())
        for model_id, backend in get_all_models().items():
            assert backend in backends, f"{model_id} maps to unknown backend {backend}"

    def test_contains_all_registry_models(self):
        """Every model in BACKEND_MODELS should appear in get_all_models()."""
        all_models = get_all_models()
        for backend, models in BACKEND_MODELS.items():
            for model_id in models:
                assert model_id in all_models, f"{model_id} missing from get_all_models()"
                assert all_models[model_id] == backend

    def test_no_duplicate_model_ids(self):
        """No model ID should appear in multiple backends."""
        seen: dict[str, str] = {}
        for backend, models in BACKEND_MODELS.items():
            for model_id in models:
                assert model_id not in seen, (
                    f"{model_id} in both {seen[model_id]} and {backend}"
                )
                seen[model_id] = backend


class TestRegistrySyncWithDocs:
    """Verify BACKEND_MODELS stays in sync with docs/models.md."""

    _DOCS_PATH = Path(__file__).resolve().parent.parent / "docs" / "models.md"

    # Section heading → backend mapping
    _SECTION_BACKENDS = {
        "google": "google",
        "fal": "fal",
        "replicate": "replicate",
    }

    @staticmethod
    def _parse_model_ids_from_docs(path: Path) -> dict[str, str]:
        """Parse model IDs from docs/models.md tables.

        Only extracts from tables whose header row starts with '| Model ID'.
        Maps each model to its backend based on the most recent
        '## Provider (`backend: xxx`)' heading.

        Returns:
            {model_id: backend} for every model documented.
        """
        content = path.read_text()
        models: dict[str, str] = {}
        current_backend: str | None = None
        in_model_table = False

        for line in content.splitlines():
            # Detect backend from top-level headings
            heading = re.match(r"^## .+\(`backend: (\w+)`\)", line)
            if heading:
                current_backend = heading.group(1)
                in_model_table = False
                continue

            # Detect table headers with "Model ID" as first column
            if re.match(r"^\| Model ID\b", line):
                in_model_table = True
                continue

            # Separator row (|---|---| etc.)
            if re.match(r"^\|[-| ]+\|$", line):
                continue

            # Non-table line ends the current table
            if not line.startswith("|"):
                in_model_table = False
                continue

            # Skip lines until we know the backend and are in a model table
            if current_backend is None or not in_model_table:
                continue

            # Extract model ID from first column (backtick-quoted)
            row_match = re.match(r"^\| `([^`]+)`", line)
            if row_match:
                model_id = row_match.group(1)
                models[model_id] = current_backend

        return models

    def test_docs_file_exists(self):
        """docs/models.md must exist for sync checking."""
        assert self._DOCS_PATH.exists(), f"Missing {self._DOCS_PATH}"

    def test_docs_parser_finds_models(self):
        """Parser should find a reasonable number of models."""
        models = self._parse_model_ids_from_docs(self._DOCS_PATH)
        assert len(models) >= 10, f"Only found {len(models)} models in docs"

    def test_all_documented_models_in_registry(self):
        """Every model in docs/models.md should be in BACKEND_MODELS."""
        documented = self._parse_model_ids_from_docs(self._DOCS_PATH)
        all_registry = get_all_models()
        missing = {
            m: b for m, b in documented.items() if m not in all_registry
        }
        assert not missing, (
            f"Models in docs/models.md but missing from BACKEND_MODELS:\n"
            + "\n".join(f"  {b}: {m}" for m, b in sorted(missing.items()))
        )

    def test_all_registry_models_in_docs(self):
        """Every model in BACKEND_MODELS should be in docs/models.md."""
        documented = self._parse_model_ids_from_docs(self._DOCS_PATH)
        all_registry = get_all_models()
        undocumented = {
            m: b for m, b in all_registry.items() if m not in documented
        }
        assert not undocumented, (
            f"Models in BACKEND_MODELS but missing from docs/models.md:\n"
            + "\n".join(f"  {b}: {m}" for m, b in sorted(undocumented.items()))
        )
