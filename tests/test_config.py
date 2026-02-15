# ABOUTME: Tests for storyboard_gen.config.
# ABOUTME: Validates YAML loading, parsing, and error handling.

import pytest
import yaml

from storyboard_gen.config import ConfigError, get_env_config, load_project


class TestLoadProject:
    def test_load_valid_project(self, sample_project_dir):
        # Act
        project = load_project(sample_project_dir)

        # Assert
        assert project.title == "Test Project"
        assert project.aspect_ratio == "9:16"
        assert len(project.characters) == 2
        assert len(project.scenes) == 3

    def test_load_minimal_project(self, minimal_project_yaml):
        # Act
        project = load_project(minimal_project_yaml)

        # Assert
        assert project.title == "Minimal"
        assert project.aspect_ratio == "16:9"  # default
        assert len(project.scenes) == 1

    def test_load_missing_yaml_raises_config_error(self, tmp_path):
        # Act & Assert
        with pytest.raises(ConfigError, match="No project.yaml found"):
            load_project(tmp_path)

    def test_load_empty_yaml_raises_config_error(self, tmp_path):
        # Arrange
        (tmp_path / "project.yaml").write_text("")

        # Act & Assert
        with pytest.raises(ConfigError, match="must be a YAML mapping"):
            load_project(tmp_path)

    def test_load_yaml_without_title_raises_config_error(self, tmp_path):
        # Arrange
        data = {
            "scenes": [{"number": 1, "type": "still", "prompt": "x", "duration": 3}]
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="title"):
            load_project(tmp_path)

    def test_load_yaml_without_scenes_raises_config_error(self, tmp_path):
        # Arrange
        data = {"title": "Empty", "scenes": []}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="at least one scene"):
            load_project(tmp_path)

    def test_load_yaml_with_invalid_aspect_ratio_raises_config_error(self, tmp_path):
        # Arrange
        data = {
            "title": "Bad Ratio",
            "aspect_ratio": "3:2",
            "scenes": [{"number": 1, "type": "still", "prompt": "x", "duration": 3}],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="Invalid aspect_ratio"):
            load_project(tmp_path)

    def test_load_yaml_with_invalid_scene_type_raises_config_error(self, tmp_path):
        # Arrange
        data = {
            "title": "Bad Type",
            "scenes": [
                {"number": 1, "type": "animation", "prompt": "x", "duration": 3}
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="invalid type"):
            load_project(tmp_path)

    def test_load_yaml_with_invalid_ken_burns_raises_config_error(self, tmp_path):
        # Arrange
        data = {
            "title": "Bad KB",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "ken_burns": "spin",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="invalid ken_burns"):
            load_project(tmp_path)

    def test_load_yaml_with_unknown_character_ref_raises_config_error(self, tmp_path):
        # Arrange
        data = {
            "title": "Bad Char",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "characters": ["nobody"],
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="unknown character 'nobody'"):
            load_project(tmp_path)


class TestProjectCharacters:
    def test_character_reference_path_resolved_relative_to_project_dir(
        self, sample_project_dir
    ):
        # Act
        project = load_project(sample_project_dir)

        # Assert
        hero = project.characters["hero"]
        assert hero.reference == sample_project_dir / "references" / "hero.png"

    def test_character_without_reference_has_none(self, sample_project_dir):
        # Act
        project = load_project(sample_project_dir)

        # Assert
        sidekick = project.characters["sidekick"]
        assert sidekick.reference is None


class TestProjectScenes:
    def test_scenes_loaded_in_order(self, sample_project_dir):
        # Act
        project = load_project(sample_project_dir)

        # Assert
        numbers = [s.number for s in project.scenes]
        assert numbers == ["1", "2", "3"]

    def test_scene_characters_validated(self, sample_project_dir):
        # Act
        project = load_project(sample_project_dir)

        # Assert
        scene1 = project.get_scene(1)
        assert scene1.characters == ["hero"]


class TestProjectProviders:
    def test_load_project_with_providers(self, tmp_path):
        # Arrange
        data = {
            "title": "Provider Test",
            "providers": {
                "still": {
                    "backend": "fal",
                    "model": "fal-ai/flux-general",
                    "options": {"strength": 0.85},
                },
                "clip": {
                    "backend": "google",
                    "model": "veo-3.1-fast-generate-001",
                },
            },
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.still_provider.backend == "fal"
        assert project.still_provider.model == "fal-ai/flux-general"
        assert project.still_provider.options["strength"] == 0.85
        assert project.clip_provider.backend == "google"
        assert project.clip_provider.model == "veo-3.1-fast-generate-001"
        assert project.clip_provider.options == {}

    def test_load_project_without_providers_defaults_to_none(self, tmp_path):
        # Arrange
        data = {
            "title": "No Providers",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.still_provider is None
        assert project.clip_provider is None

    def test_load_project_with_partial_providers(self, tmp_path):
        # Arrange — only still provider specified
        data = {
            "title": "Partial",
            "providers": {
                "still": {"backend": "replicate", "model": "flux-2-pro"},
            },
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.still_provider.backend == "replicate"
        assert project.clip_provider is None

    def test_load_project_with_invalid_backend_raises_config_error(self, tmp_path):
        # Arrange
        data = {
            "title": "Bad Backend",
            "providers": {
                "still": {"backend": "midjourney", "model": "v6"},
            },
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="Invalid provider backend"):
            load_project(tmp_path)

    def test_load_scene_with_provider_override(self, tmp_path):
        # Arrange
        data = {
            "title": "Scene Override",
            "providers": {
                "still": {"backend": "google", "model": "imagen-4.0-generate-001"},
            },
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "provider": {
                        "backend": "fal",
                        "model": "fal-ai/flux-general",
                    },
                },
                {"number": 2, "type": "still", "prompt": "y", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert — scene 1 has override, scene 2 does not
        assert project.get_scene(1).provider.backend == "fal"
        assert project.get_scene(2).provider is None


class TestSceneReferenceOverride:
    def test_load_scene_with_reference_override(self, tmp_path):
        # Arrange — scene has reference: key
        ref_file = tmp_path / "references" / "mum.png"
        ref_file.parent.mkdir()
        ref_file.write_bytes(b"fake-png")
        data = {
            "title": "Ref Override",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "Portrait of mum.",
                    "duration": 5,
                    "reference": "references/mum.png",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert — reference resolved relative to project_dir
        scene = project.get_scene(1)
        assert scene.reference == tmp_path / "references" / "mum.png"

    def test_load_scene_without_reference_defaults_to_none(self, tmp_path):
        # Arrange — no reference key
        data = {
            "title": "No Ref",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.get_scene(1).reference is None


class TestSceneModelOverride:
    def test_load_scene_with_model_override(self, tmp_path):
        # Arrange
        data = {
            "title": "Model Override",
            "providers": {
                "still": {"backend": "fal", "model": "fal-ai/flux-general"},
            },
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "A portrait.",
                    "duration": 5,
                    "model": "fal-ai/flux-pro/kontext",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        scene = project.get_scene(1)
        assert scene.model == "fal-ai/flux-pro/kontext"
        assert scene.provider is None

    def test_load_scene_with_model_and_provider_raises(self, tmp_path):
        # Arrange — both model and provider on same scene
        data = {
            "title": "Conflict",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "model": "fal-ai/flux-pro/kontext",
                    "provider": {
                        "backend": "fal",
                        "model": "fal-ai/flux-general",
                    },
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(
            ConfigError, match="cannot specify both 'model' and 'provider'"
        ):
            load_project(tmp_path)

    def test_load_scene_without_model_defaults_to_none(self, tmp_path):
        # Arrange
        data = {
            "title": "No Model",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.get_scene(1).model is None


class TestProjectDuration:
    def test_load_project_preserves_float_duration(self, tmp_path):
        # Arrange
        data = {
            "title": "Float Duration",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 2.5},
                {"number": 2, "type": "still", "prompt": "y", "duration": 3.7},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.get_scene(1).duration == 2.5
        assert project.get_scene(2).duration == 3.7


class TestProjectAudio:
    def test_load_project_with_audio_resolves_path(self, tmp_path):
        # Arrange
        data = {
            "title": "Audio Test",
            "audio": "audio.m4a",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.audio == tmp_path / "audio.m4a"

    def test_load_project_without_audio_defaults_to_none(self, tmp_path):
        # Arrange
        data = {
            "title": "No Audio",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.audio is None


class TestGetEnvConfig:
    def test_get_env_config_reads_dotenv_from_cwd(self, tmp_path, monkeypatch):
        # Arrange: create .env in a temp dir and chdir to it
        env_file = tmp_path / ".env"
        env_file.write_text(
            "USE_VERTEX=true\n"
            "GOOGLE_CLOUD_PROJECT=test-project\n"
            "GOOGLE_CLOUD_LOCATION=us-central1\n"
            "GCS_OUTPUT_BUCKET=gs://test-bucket/\n"
        )
        monkeypatch.chdir(tmp_path)
        # Clear any existing env vars so only .env is used
        monkeypatch.delenv("USE_VERTEX", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("GCS_OUTPUT_BUCKET", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        # Act
        config = get_env_config()

        # Assert
        assert config["use_vertex"] is True
        assert config["project"] == "test-project"
        assert config["location"] == "us-central1"
        assert config["gcs_bucket"] == "gs://test-bucket/"

    def test_get_env_config_defaults_without_dotenv(self, tmp_path, monkeypatch):
        # Arrange: chdir to a dir with no .env
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("USE_VERTEX", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        monkeypatch.delenv("GCS_OUTPUT_BUCKET", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        # Act
        config = get_env_config()

        # Assert
        assert config["use_vertex"] is False
        assert config["project"] is None
