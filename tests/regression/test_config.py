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

    def test_load_yaml_with_invalid_camera_raises_config_error(self, tmp_path):
        # Arrange
        data = {
            "title": "Bad Camera",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "camera": "WDIE",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="invalid camera"):
            load_project(tmp_path)

    def test_load_yaml_with_valid_camera_succeeds(self, tmp_path):
        # Arrange
        data = {
            "title": "Good Camera",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "camera": "WIDE",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.scenes[0].camera == "WIDE"

    def test_load_yaml_with_lowercase_camera_normalizes(self, tmp_path):
        # Arrange
        data = {
            "title": "Lowercase Camera",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "camera": "close",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert — stored as uppercase
        assert project.scenes[0].camera == "CLOSE"

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
        assert hero.reference == [sample_project_dir / "references" / "hero.png"]

    def test_character_without_reference_has_empty_list(self, sample_project_dir):
        # Act
        project = load_project(sample_project_dir)

        # Assert
        sidekick = project.characters["sidekick"]
        assert sidekick.reference == []

    def test_character_with_multiple_references(self, tmp_path):
        # Arrange
        data = {
            "title": "Multi Ref",
            "characters": {
                "hero": {
                    "description": "A hero",
                    "reference": [
                        "references/front.png",
                        "references/side.png",
                    ],
                },
            },
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "characters": ["hero"],
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        hero = project.characters["hero"]
        assert len(hero.reference) == 2
        assert hero.reference[0] == tmp_path / "references" / "front.png"
        assert hero.reference[1] == tmp_path / "references" / "side.png"

    def test_character_string_reference_raises_config_error(self, tmp_path):
        # Arrange — string reference (old format) should produce clear error
        data = {
            "title": "Old Format",
            "characters": {
                "hero": {
                    "description": "A hero",
                    "reference": "references/hero.png",
                },
            },
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "characters": ["hero"],
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="must be a list since v0.29.0"):
            load_project(tmp_path)

    def test_character_string_reference_error_includes_migration_hint(self, tmp_path):
        # Arrange
        data = {
            "title": "Old Format",
            "characters": {
                "hero": {
                    "description": "A hero",
                    "reference": "references/hero.png",
                },
            },
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "characters": ["hero"],
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert — error message includes migration instructions
        with pytest.raises(ConfigError, match="references/hero.png"):
            load_project(tmp_path)


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

    def test_load_provider_with_pricing_override(self, tmp_path):
        """Provider pricing override is parsed into ProviderConfig."""
        # Arrange
        data = {
            "title": "Pricing Override",
            "providers": {
                "still": {
                    "backend": "fal",
                    "model": "fal-ai/flux-general",
                    "pricing": {
                        "unit_price": 0.99,
                        "unit": "image",
                        "currency": "EUR",
                    },
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
        assert project.still_provider.pricing is not None
        assert project.still_provider.pricing["unit_price"] == 0.99
        assert project.still_provider.pricing["unit"] == "image"
        assert project.still_provider.pricing["currency"] == "EUR"

    def test_load_provider_without_pricing_defaults_to_none(self, tmp_path):
        """Provider without pricing field has pricing=None."""
        # Arrange
        data = {
            "title": "No Pricing",
            "providers": {
                "still": {"backend": "fal", "model": "fal-ai/flux-general"},
            },
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.still_provider.pricing is None

    def test_load_provider_pricing_defaults_currency_to_usd(self, tmp_path):
        """Pricing override without currency defaults to USD."""
        # Arrange
        data = {
            "title": "Default Currency",
            "providers": {
                "clip": {
                    "backend": "google",
                    "model": "veo-3.1-fast-generate-001",
                    "pricing": {"unit_price": 0.20, "unit": "second"},
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
        assert project.clip_provider.pricing["currency"] == "USD"

    def test_load_provider_pricing_ignores_incomplete_override(self, tmp_path):
        """Pricing override missing required fields is ignored."""
        # Arrange — no unit_price
        data = {
            "title": "Incomplete Pricing",
            "providers": {
                "still": {
                    "backend": "fal",
                    "model": "fal-ai/flux-general",
                    "pricing": {"unit": "image"},
                },
            },
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert — incomplete pricing is ignored
        assert project.still_provider.pricing is None


class TestSceneReferenceOverride:
    def test_load_scene_with_reference_override(self, tmp_path):
        # Arrange — scene has reference: list
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
                    "reference": ["references/mum.png"],
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert — reference resolved relative to project_dir
        scene = project.get_scene(1)
        assert scene.reference == [tmp_path / "references" / "mum.png"]

    def test_load_scene_with_multiple_references(self, tmp_path):
        # Arrange
        data = {
            "title": "Multi Ref Scene",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "reference": ["refs/front.png", "refs/side.png"],
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        scene = project.get_scene(1)
        assert len(scene.reference) == 2
        assert scene.reference[0] == tmp_path / "refs" / "front.png"
        assert scene.reference[1] == tmp_path / "refs" / "side.png"

    def test_load_scene_without_reference_defaults_to_empty_list(self, tmp_path):
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
        assert project.get_scene(1).reference == []

    def test_scene_string_reference_raises_config_error(self, tmp_path):
        # Arrange — string reference (old format) should produce clear error
        data = {
            "title": "Old Format",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "reference": "references/mum.png",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="must be a list since v0.29.0"):
            load_project(tmp_path)


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


class TestVeoClipFields:
    """Tests for new Veo 3.1 clip generation fields (source_frame, last_frame, etc.)."""

    def test_load_scene_with_source_frame(self, tmp_path):
        # Arrange
        data = {
            "title": "Source Frame",
            "scenes": [
                {
                    "number": 1,
                    "type": "clip",
                    "prompt": "Animate.",
                    "duration": 5,
                    "source_frame": "output/stills/scene_01.png",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert — path resolved relative to project_dir
        scene = project.get_scene(1)
        assert scene.source_frame == tmp_path / "output/stills/scene_01.png"

    def test_source_frame_on_still_raises(self, tmp_path):
        # Arrange — source_frame only valid on clips
        data = {
            "title": "Bad",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "source_frame": "output/stills/scene_01.png",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="source_frame.*only valid on clip"):
            load_project(tmp_path)

    def test_load_scene_with_last_frame(self, tmp_path):
        # Arrange
        data = {
            "title": "Last Frame",
            "scenes": [
                {
                    "number": 1,
                    "type": "clip",
                    "prompt": "Interpolate.",
                    "duration": 5,
                    "source_frame": "output/stills/scene_01.png",
                    "last_frame": "output/stills/scene_02.png",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        scene = project.get_scene(1)
        assert scene.last_frame == tmp_path / "output/stills/scene_02.png"

    def test_last_frame_without_source_frame_raises(self, tmp_path):
        # Arrange — last_frame requires source_frame
        data = {
            "title": "Bad",
            "scenes": [
                {
                    "number": 1,
                    "type": "clip",
                    "prompt": "x",
                    "duration": 3,
                    "last_frame": "output/stills/scene_02.png",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="last_frame.*requires source_frame"):
            load_project(tmp_path)

    def test_last_frame_on_still_raises(self, tmp_path):
        # Arrange — last_frame only valid on clips
        data = {
            "title": "Bad",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "source_frame": "x.png",
                    "last_frame": "y.png",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="source_frame.*only valid on clip"):
            load_project(tmp_path)

    def test_load_scene_with_extend_from(self, tmp_path):
        # Arrange
        data = {
            "title": "Extend",
            "scenes": [
                {
                    "number": 2,
                    "type": "clip",
                    "prompt": "Continue.",
                    "duration": 5,
                    "extend_from": "1",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        scene = project.get_scene(2)
        assert scene.extend_from == "1"

    def test_extend_from_on_still_raises(self, tmp_path):
        # Arrange
        data = {
            "title": "Bad",
            "scenes": [
                {
                    "number": 2,
                    "type": "still",
                    "prompt": "x",
                    "duration": 3,
                    "extend_from": "1",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="extend_from.*only valid on clip"):
            load_project(tmp_path)

    def test_extend_from_and_source_frame_mutually_exclusive(self, tmp_path):
        # Arrange — both set on the same scene
        data = {
            "title": "Bad",
            "scenes": [
                {
                    "number": 2,
                    "type": "clip",
                    "prompt": "x",
                    "duration": 3,
                    "source_frame": "output/stills/scene_01.png",
                    "extend_from": "1",
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="mutually exclusive"):
            load_project(tmp_path)

    def test_load_scene_with_seed(self, tmp_path):
        # Arrange
        data = {
            "title": "Seeded",
            "scenes": [
                {
                    "number": 1,
                    "type": "clip",
                    "prompt": "Deterministic.",
                    "duration": 5,
                    "seed": 42,
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.get_scene(1).seed == 42

    def test_load_scene_with_variants(self, tmp_path):
        # Arrange
        data = {
            "title": "Variants",
            "scenes": [
                {
                    "number": 1,
                    "type": "clip",
                    "prompt": "Multi-take.",
                    "duration": 5,
                    "variants": 3,
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.get_scene(1).variants == 3

    def test_variants_below_one_raises(self, tmp_path):
        # Arrange
        data = {
            "title": "Bad",
            "scenes": [
                {
                    "number": 1,
                    "type": "clip",
                    "prompt": "x",
                    "duration": 3,
                    "variants": 0,
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="variants.*must be between 1 and 4"):
            load_project(tmp_path)

    def test_variants_above_four_raises(self, tmp_path):
        # Arrange
        data = {
            "title": "Bad",
            "scenes": [
                {
                    "number": 1,
                    "type": "clip",
                    "prompt": "x",
                    "duration": 3,
                    "variants": 5,
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="variants.*must be between 1 and 4"):
            load_project(tmp_path)

    def test_scene_without_new_fields_defaults_correctly(self, tmp_path):
        # Arrange — backward compatibility: no new fields
        data = {
            "title": "Compat",
            "scenes": [
                {"number": 1, "type": "clip", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert — all new fields at defaults
        scene = project.get_scene(1)
        assert scene.source_frame is None
        assert scene.last_frame is None
        assert scene.extend_from is None
        assert scene.seed is None
        assert scene.variants == 1

    def test_extend_from_integer_parsed_as_string(self, tmp_path):
        # Arrange — YAML may parse "1" as integer
        data = {
            "title": "Int Extend",
            "scenes": [
                {
                    "number": 2,
                    "type": "clip",
                    "prompt": "Continue.",
                    "duration": 5,
                    "extend_from": 1,
                },
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert — parsed as string
        assert project.get_scene(2).extend_from == "1"


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


class TestProjectSubtitles:
    def test_load_project_with_subtitles_resolves_path(self, tmp_path):
        # Arrange
        data = {
            "title": "Subtitles Test",
            "subtitles": "subs/voiceover.srt",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.subtitles == tmp_path / "subs" / "voiceover.srt"

    def test_load_project_without_subtitles_defaults_to_none(self, tmp_path):
        # Arrange
        data = {
            "title": "No Subtitles",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.subtitles is None


class TestStyleReference:
    def test_load_project_with_style_reference(self, tmp_path):
        # Arrange
        data = {
            "title": "Style Ref",
            "style_reference": ["references/style.jpg"],
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert — path resolved relative to project_dir
        assert project.style_reference == [tmp_path / "references" / "style.jpg"]

    def test_load_project_without_style_reference_defaults_to_empty(self, tmp_path):
        # Arrange
        data = {
            "title": "No Style Ref",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert project.style_reference == []

    def test_load_project_with_multiple_style_references(self, tmp_path):
        # Arrange
        data = {
            "title": "Multi Style Ref",
            "style_reference": ["refs/style1.jpg", "refs/style2.png"],
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act
        project = load_project(tmp_path)

        # Assert
        assert len(project.style_reference) == 2
        assert project.style_reference[0] == tmp_path / "refs" / "style1.jpg"
        assert project.style_reference[1] == tmp_path / "refs" / "style2.png"

    def test_load_project_with_string_style_reference_raises(self, tmp_path):
        # Arrange — string instead of list
        data = {
            "title": "Bad Style Ref",
            "style_reference": "references/style.jpg",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 3},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Act & Assert
        with pytest.raises(ConfigError, match="style_reference.*must be a list"):
            load_project(tmp_path)


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
