# ABOUTME: Tests for the YAML editor helper functions.
# ABOUTME: Covers format-preserving load/save and nested dict operations.

import pytest

ruamel_yaml = pytest.importorskip("ruamel.yaml")

from storyboard_gen.gui.yaml_editor_helpers import (  # noqa: E402
    get_nested,
    load_yaml_roundtrip,
    save_yaml_roundtrip,
    update_nested,
)


@pytest.fixture
def sample_yaml(tmp_path):
    """Create a sample YAML file with comments for round-trip testing."""
    content = """\
# Project config
title: My Project
aspect_ratio: "16:9"
providers:
  still:
    backend: google
    model: imagen-4.0-generate-001
  clip:
    backend: fal
    model: fal-ai/wan/v2.1/text-to-video
characters:
  hero:
    description: A brave warrior
"""
    path = tmp_path / "project.yaml"
    path.write_text(content)
    return path


class TestLoadYamlRoundtrip:
    """Tests for load_yaml_roundtrip()."""

    def test_loads_title(self, sample_yaml):
        """Should load the title field."""
        data = load_yaml_roundtrip(sample_yaml)
        assert data["title"] == "My Project"

    def test_loads_nested_provider(self, sample_yaml):
        """Should load nested provider config."""
        data = load_yaml_roundtrip(sample_yaml)
        assert data["providers"]["still"]["backend"] == "google"

    def test_preserves_comments(self, sample_yaml):
        """Round-trip should preserve YAML comments."""
        data = load_yaml_roundtrip(sample_yaml)
        save_yaml_roundtrip(data, sample_yaml)
        text = sample_yaml.read_text()
        assert "# Project config" in text


class TestSaveYamlRoundtrip:
    """Tests for save_yaml_roundtrip()."""

    def test_save_and_reload(self, sample_yaml):
        """Saved data should be loadable again."""
        data = load_yaml_roundtrip(sample_yaml)
        data["title"] = "Changed Title"
        save_yaml_roundtrip(data, sample_yaml)

        reloaded = load_yaml_roundtrip(sample_yaml)
        assert reloaded["title"] == "Changed Title"

    def test_preserves_ordering(self, sample_yaml):
        """Key ordering should be preserved after save."""
        data = load_yaml_roundtrip(sample_yaml)
        save_yaml_roundtrip(data, sample_yaml)

        text = sample_yaml.read_text()
        title_pos = text.index("title:")
        aspect_pos = text.index("aspect_ratio:")
        assert title_pos < aspect_pos


class TestUpdateNested:
    """Tests for update_nested()."""

    def test_set_existing_key(self):
        """Should update an existing nested key."""
        data = {"providers": {"still": {"backend": "google"}}}
        update_nested(data, ["providers", "still", "backend"], "fal")
        assert data["providers"]["still"]["backend"] == "fal"

    def test_creates_intermediate_dicts(self):
        """Should create intermediate dicts when path doesn't exist."""
        data = {}
        update_nested(data, ["providers", "still", "backend"], "google")
        assert data["providers"]["still"]["backend"] == "google"

    def test_removes_key_for_none(self):
        """Should remove the key when value is None."""
        data = {"providers": {"still": {"backend": "google", "options": {"x": 1}}}}
        update_nested(data, ["providers", "still", "options"], None)
        assert "options" not in data["providers"]["still"]

    def test_remove_nonexistent_key_is_noop(self):
        """Removing a non-existent key should not raise."""
        data = {"providers": {"still": {"backend": "google"}}}
        update_nested(data, ["providers", "still", "options"], None)
        assert "options" not in data["providers"]["still"]


class TestGetNested:
    """Tests for get_nested()."""

    def test_get_existing_value(self):
        """Should return the value at the given path."""
        data = {"providers": {"still": {"backend": "google"}}}
        assert get_nested(data, ["providers", "still", "backend"]) == "google"

    def test_returns_default_for_missing_path(self):
        """Should return default when path doesn't exist."""
        data = {"providers": {}}
        assert (
            get_nested(data, ["providers", "still", "backend"], "fallback")
            == "fallback"
        )

    def test_returns_default_for_non_dict_intermediate(self):
        """Should return default when intermediate value isn't a dict."""
        data = {"providers": "not-a-dict"}
        assert (
            get_nested(data, ["providers", "still", "backend"], "fallback")
            == "fallback"
        )

    def test_returns_none_by_default(self):
        """Default return value should be None."""
        data = {}
        assert get_nested(data, ["missing", "path"]) is None
