# ABOUTME: Tests for storyboard_gen.models.
# ABOUTME: Validates Project, Scene, and Character dataclasses.

from pathlib import Path

from storyboard_gen.models import (
    CAMERA_PROMPTS,
    Character,
    Project,
    ProviderConfig,
    Scene,
)


class TestCharacter:
    def test_character_creation_with_all_fields(self):
        # Arrange & Act
        char = Character(
            id="hero", description="A brave lad", reference=[Path("ref.png")]
        )

        # Assert
        assert char.id == "hero"
        assert char.description == "A brave lad"
        assert char.reference == [Path("ref.png")]

    def test_character_creation_without_reference(self):
        # Arrange & Act
        char = Character(id="extra", description="Background character")

        # Assert
        assert char.reference == []

    def test_character_creation_with_multiple_references(self):
        # Arrange & Act
        char = Character(
            id="hero",
            description="A brave lad",
            reference=[Path("front.png"), Path("side.png"), Path("detail.png")],
        )

        # Assert
        assert len(char.reference) == 3
        assert char.reference[0] == Path("front.png")
        assert char.reference[2] == Path("detail.png")

    def test_character_is_frozen(self):
        # Arrange
        char = Character(id="hero", description="test")

        # Act & Assert
        try:
            char.id = "villain"
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass


class TestProviderConfig:
    def test_provider_config_creation(self):
        # Arrange & Act
        cfg = ProviderConfig(backend="fal", model="fal-ai/flux-general")

        # Assert
        assert cfg.backend == "fal"
        assert cfg.model == "fal-ai/flux-general"
        assert cfg.options == {}

    def test_provider_config_with_options(self):
        # Arrange & Act
        cfg = ProviderConfig(
            backend="fal",
            model="fal-ai/flux-general",
            options={"strength": 0.85, "num_inference_steps": 28},
        )

        # Assert
        assert cfg.options["strength"] == 0.85
        assert cfg.options["num_inference_steps"] == 28

    def test_provider_config_is_frozen(self):
        # Arrange
        cfg = ProviderConfig(backend="google", model="imagen-4.0-generate-001")

        # Act & Assert
        try:
            cfg.backend = "fal"
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass


class TestScene:
    def test_scene_creation_with_defaults(self):
        # Arrange & Act
        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="A thing.", duration=5
        )

        # Assert
        assert scene.number == "1"
        assert scene.camera is None
        assert scene.ken_burns is None
        assert scene.characters == []
        assert scene.provider is None

    def test_scene_creation_with_all_fields(self):
        # Arrange & Act
        scene = Scene(
            number="3",
            title="Action",
            scene_type="clip",
            prompt="Running.",
            duration=8,
            camera="WIDE",
            ken_burns="zoom_in",
            characters=["hero", "sidekick"],
            provider=ProviderConfig(backend="fal", model="fal-ai/flux-general"),
        )

        # Assert
        assert scene.scene_type == "clip"
        assert scene.ken_burns == "zoom_in"
        assert len(scene.characters) == 2
        assert scene.provider.backend == "fal"

    def test_scene_creation_with_float_duration(self):
        # Arrange & Act
        scene = Scene(
            number="1",
            title="Test",
            scene_type="still",
            prompt="A thing.",
            duration=2.5,
        )

        # Assert
        assert scene.duration == 2.5
        assert isinstance(scene.duration, float)

    def test_scene_creation_with_model_override(self):
        # Arrange & Act
        scene = Scene(
            number="1",
            title="Kontext scene",
            scene_type="still",
            prompt="A portrait.",
            duration=5,
            model="fal-ai/flux-pro/kontext",
        )

        # Assert
        assert scene.model == "fal-ai/flux-pro/kontext"
        assert scene.provider is None

    def test_scene_model_defaults_to_none(self):
        # Arrange & Act
        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="x", duration=5
        )

        # Assert
        assert scene.model is None

    def test_scene_creation_with_reference_override(self):
        # Arrange & Act
        scene = Scene(
            number="1",
            title="Override",
            scene_type="still",
            prompt="Portrait.",
            duration=5,
            reference=[Path("references/mum.png")],
        )

        # Assert
        assert scene.reference == [Path("references/mum.png")]

    def test_scene_creation_with_multiple_references(self):
        # Arrange & Act
        scene = Scene(
            number="1",
            title="Multi-ref",
            scene_type="still",
            prompt="Portrait.",
            duration=5,
            reference=[Path("front.png"), Path("side.png")],
        )

        # Assert
        assert len(scene.reference) == 2

    def test_scene_reference_defaults_to_empty_list(self):
        # Arrange & Act
        scene = Scene(
            number="1", title="Test", scene_type="still", prompt="x", duration=5
        )

        # Assert
        assert scene.reference == []

    def test_scene_source_frame_defaults_to_none(self):
        # Arrange & Act
        scene = Scene(
            number="1", title="Test", scene_type="clip", prompt="x", duration=5
        )

        # Assert
        assert scene.source_frame is None

    def test_scene_creation_with_source_frame(self):
        # Arrange & Act
        scene = Scene(
            number="1",
            title="Animated",
            scene_type="clip",
            prompt="Action.",
            duration=5,
            source_frame=Path("output/stills/scene_01.png"),
        )

        # Assert
        assert scene.source_frame == Path("output/stills/scene_01.png")

    def test_scene_last_frame_defaults_to_none(self):
        # Arrange & Act
        scene = Scene(
            number="1", title="Test", scene_type="clip", prompt="x", duration=5
        )

        # Assert
        assert scene.last_frame is None

    def test_scene_creation_with_last_frame(self):
        # Arrange & Act
        scene = Scene(
            number="1",
            title="Interpolated",
            scene_type="clip",
            prompt="Transition.",
            duration=5,
            source_frame=Path("output/stills/scene_01.png"),
            last_frame=Path("output/stills/scene_02.png"),
        )

        # Assert
        assert scene.last_frame == Path("output/stills/scene_02.png")

    def test_scene_extend_from_defaults_to_none(self):
        # Arrange & Act
        scene = Scene(
            number="2", title="Test", scene_type="clip", prompt="x", duration=5
        )

        # Assert
        assert scene.extend_from is None

    def test_scene_creation_with_extend_from(self):
        # Arrange & Act
        scene = Scene(
            number="2",
            title="Continuation",
            scene_type="clip",
            prompt="Continue.",
            duration=5,
            extend_from="1",
        )

        # Assert
        assert scene.extend_from == "1"

    def test_scene_seed_defaults_to_none(self):
        # Arrange & Act
        scene = Scene(
            number="1", title="Test", scene_type="clip", prompt="x", duration=5
        )

        # Assert
        assert scene.seed is None

    def test_scene_creation_with_seed(self):
        # Arrange & Act
        scene = Scene(
            number="1",
            title="Seeded",
            scene_type="clip",
            prompt="Deterministic.",
            duration=5,
            seed=42,
        )

        # Assert
        assert scene.seed == 42

    def test_scene_variants_defaults_to_one(self):
        # Arrange & Act
        scene = Scene(
            number="1", title="Test", scene_type="clip", prompt="x", duration=5
        )

        # Assert
        assert scene.variants == 1

    def test_scene_creation_with_variants(self):
        # Arrange & Act
        scene = Scene(
            number="1",
            title="Multi-take",
            scene_type="clip",
            prompt="Action.",
            duration=5,
            variants=3,
        )

        # Assert
        assert scene.variants == 3


class TestProject:
    def _make_project(self) -> Project:
        """Helper to create a minimal project for testing."""
        chars = {
            "hero": Character(id="hero", description="The hero"),
        }
        scenes = [
            Scene(number="1", title="S1", scene_type="still", prompt="P1", duration=5),
            Scene(number="2", title="S2", scene_type="clip", prompt="P2", duration=6),
            Scene(number="3", title="S3", scene_type="still", prompt="P3", duration=4),
        ]
        return Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Watercolour style.",
            characters=chars,
            scenes=scenes,
        )

    def test_project_with_provider_configs(self):
        # Arrange & Act
        project = Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters={},
            scenes=[
                Scene(
                    number="1", title="S1", scene_type="still", prompt="P", duration=5
                )
            ],
            still_provider=ProviderConfig(backend="fal", model="fal-ai/flux-general"),
            clip_provider=ProviderConfig(
                backend="google", model="veo-3.1-fast-generate-001"
            ),
        )

        # Assert
        assert project.still_provider.backend == "fal"
        assert project.clip_provider.backend == "google"

    def test_project_provider_defaults_to_none(self):
        # Arrange & Act
        project = Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters={},
            scenes=[
                Scene(
                    number="1", title="S1", scene_type="still", prompt="P", duration=5
                )
            ],
        )

        # Assert
        assert project.still_provider is None
        assert project.clip_provider is None

    def test_get_scene_returns_correct_scene(self):
        # Arrange
        project = self._make_project()

        # Act
        scene = project.get_scene("2")

        # Assert
        assert scene.title == "S2"

    def test_get_scene_raises_for_missing_number(self):
        # Arrange
        project = self._make_project()

        # Act & Assert
        try:
            project.get_scene("99")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "99" in str(e)

    def test_get_stills_returns_only_stills(self):
        # Arrange
        project = self._make_project()

        # Act
        stills = project.get_stills()

        # Assert
        assert len(stills) == 2
        assert all(s.scene_type == "still" for s in stills)

    def test_get_clips_returns_only_clips(self):
        # Arrange
        project = self._make_project()

        # Act
        clips = project.get_clips()

        # Assert
        assert len(clips) == 1
        assert clips[0].scene_type == "clip"

    def test_build_prompt_prepends_style_prefix(self):
        # Arrange
        project = self._make_project()
        scene = project.get_scene("1")

        # Act
        prompt = project.build_prompt(scene)

        # Assert
        assert prompt.startswith("Watercolour style.")
        assert "P1" in prompt

    def test_build_prompt_with_standard_camera_injects_phrasing(self):
        """Standard camera values are mapped to descriptive prompt phrasings."""
        # Arrange
        scene = Scene(
            number="1",
            title="Wide",
            scene_type="still",
            prompt="A sunset.",
            duration=5,
            camera="WIDE",
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Painterly.",
            characters={},
            scenes=[scene],
        )

        # Act
        prompt = project.build_prompt(scene)

        # Assert — camera phrasing injected between style and scene prompt
        assert CAMERA_PROMPTS["WIDE"] in prompt
        assert prompt.startswith("Painterly.")
        assert prompt.endswith("A sunset.")

    def test_build_prompt_with_camera_none_unchanged(self):
        """No camera → no camera phrasing injected (backwards compatible)."""
        # Arrange
        scene = Scene(
            number="1",
            title="No cam",
            scene_type="still",
            prompt="A sunset.",
            duration=5,
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Painterly.",
            characters={},
            scenes=[scene],
        )

        # Act
        prompt = project.build_prompt(scene)

        # Assert — same as before: style + scene prompt
        assert prompt == "Painterly. A sunset."

    def test_build_prompt_camera_before_characters(self):
        """Camera phrasing should appear before character descriptions."""
        # Arrange
        chars = {
            "hero": Character(id="hero", description="A tall boy"),
        }
        scene = Scene(
            number="1",
            title="Ordered",
            scene_type="still",
            prompt="Walking.",
            duration=5,
            camera="CLOSE",
            characters=["hero"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters=chars,
            scenes=[scene],
        )

        # Act
        prompt = project.build_prompt(scene)

        # Assert — order: style, camera, characters, scene prompt
        camera_pos = prompt.index(CAMERA_PROMPTS["CLOSE"])
        chars_pos = prompt.index("Characters:")
        scene_pos = prompt.index("Walking.")
        assert camera_pos < chars_pos < scene_pos

    def test_build_prompt_camera_case_insensitive(self):
        """Camera lookup should be case-insensitive."""
        # Arrange
        scene = Scene(
            number="1",
            title="Case",
            scene_type="still",
            prompt="A scene.",
            duration=5,
            camera="wide",
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters={},
            scenes=[scene],
        )

        # Act
        prompt = project.build_prompt(scene)

        # Assert — same phrasing as uppercase WIDE
        assert CAMERA_PROMPTS["WIDE"] in prompt

    def test_camera_prompts_contains_all_standard_values(self):
        """CAMERA_PROMPTS dict should contain all 12 standard camera values."""
        # Arrange & Act & Assert
        expected = {
            "EWS",
            "WIDE",
            "MEDIUM",
            "MCU",
            "CLOSE",
            "ECU",
            "POV",
            "LOW",
            "HIGH",
            "OVERHEAD",
            "OTS",
            "DUTCH",
        }
        assert set(CAMERA_PROMPTS.keys()) == expected

    def test_get_reference_images_returns_existing_refs(self, tmp_path):
        # Arrange
        ref_path = tmp_path / "hero.png"
        ref_path.write_bytes(b"fake")
        chars = {
            "hero": Character(id="hero", description="Hero", reference=[ref_path]),
            "ghost": Character(
                id="ghost",
                description="Ghost",
                reference=[tmp_path / "nope.png"],
            ),
        }
        scene = Scene(
            number="1",
            title="T",
            scene_type="still",
            prompt="P",
            duration=5,
            characters=["hero", "ghost"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="",
            characters=chars,
            scenes=[scene],
        )

        # Act
        refs = project.get_reference_images(scene)

        # Assert — only existing ref returned
        assert len(refs) == 1
        assert refs[0] == ref_path

    def test_get_reference_images_uses_scene_override(self, tmp_path):
        # Arrange — scene.reference overrides character refs
        scene_ref = tmp_path / "scene_override.png"
        scene_ref.write_bytes(b"fake")
        char_ref = tmp_path / "hero.png"
        char_ref.write_bytes(b"fake")
        chars = {
            "hero": Character(id="hero", description="Hero", reference=[char_ref]),
        }
        scene = Scene(
            number="1",
            title="T",
            scene_type="still",
            prompt="P",
            duration=5,
            characters=["hero"],
            reference=[scene_ref],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="",
            characters=chars,
            scenes=[scene],
        )

        # Act
        refs = project.get_reference_images(scene)

        # Assert — scene override replaces character refs
        assert len(refs) == 1
        assert refs[0] == scene_ref

    def test_get_reference_images_multi_scene_refs(self, tmp_path):
        # Arrange — scene with multiple reference images
        ref1 = tmp_path / "front.png"
        ref2 = tmp_path / "side.png"
        ref3 = tmp_path / "missing.png"
        ref1.write_bytes(b"fake")
        ref2.write_bytes(b"fake")
        scene = Scene(
            number="1",
            title="T",
            scene_type="still",
            prompt="P",
            duration=5,
            reference=[ref1, ref2, ref3],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="",
            characters={},
            scenes=[scene],
        )

        # Act
        refs = project.get_reference_images(scene)

        # Assert — only existing refs returned
        assert len(refs) == 2
        assert refs[0] == ref1
        assert refs[1] == ref2

    def test_get_reference_images_multi_character_refs(self, tmp_path):
        # Arrange — two characters each with multiple refs
        hero_front = tmp_path / "hero_front.png"
        hero_side = tmp_path / "hero_side.png"
        villain_ref = tmp_path / "villain.png"
        hero_front.write_bytes(b"fake")
        hero_side.write_bytes(b"fake")
        villain_ref.write_bytes(b"fake")
        chars = {
            "hero": Character(
                id="hero",
                description="Hero",
                reference=[hero_front, hero_side],
            ),
            "villain": Character(
                id="villain",
                description="Villain",
                reference=[villain_ref],
            ),
        }
        scene = Scene(
            number="1",
            title="T",
            scene_type="still",
            prompt="P",
            duration=5,
            characters=["hero", "villain"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="",
            characters=chars,
            scenes=[scene],
        )

        # Act
        refs = project.get_reference_images(scene)

        # Assert — round-robin: hero1, villain1, hero2
        assert len(refs) == 3
        assert refs == [hero_front, villain_ref, hero_side]

    def test_get_reference_images_interleaves_three_characters(self, tmp_path):
        """Three characters: A(2 refs), B(2 refs), C(1 ref) → A1, B1, C1, A2, B2."""
        # Arrange
        a1 = tmp_path / "a1.png"
        a2 = tmp_path / "a2.png"
        b1 = tmp_path / "b1.png"
        b2 = tmp_path / "b2.png"
        c1 = tmp_path / "c1.png"
        for p in [a1, a2, b1, b2, c1]:
            p.write_bytes(b"fake")
        chars = {
            "a": Character(id="a", description="A", reference=[a1, a2]),
            "b": Character(id="b", description="B", reference=[b1, b2]),
            "c": Character(id="c", description="C", reference=[c1]),
        }
        scene = Scene(
            number="1",
            title="T",
            scene_type="still",
            prompt="P",
            duration=5,
            characters=["a", "b", "c"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="",
            characters=chars,
            scenes=[scene],
        )

        # Act
        refs = project.get_reference_images(scene)

        # Assert — round-robin interleaving
        assert refs == [a1, b1, c1, a2, b2]

    def test_get_reference_images_single_character_preserves_order(self, tmp_path):
        """Single character with multiple refs — order unchanged."""
        # Arrange
        r1 = tmp_path / "r1.png"
        r2 = tmp_path / "r2.png"
        r3 = tmp_path / "r3.png"
        for p in [r1, r2, r3]:
            p.write_bytes(b"fake")
        chars = {
            "hero": Character(id="hero", description="Hero", reference=[r1, r2, r3]),
        }
        scene = Scene(
            number="1",
            title="T",
            scene_type="still",
            prompt="P",
            duration=5,
            characters=["hero"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="",
            characters=chars,
            scenes=[scene],
        )

        # Act
        refs = project.get_reference_images(scene)

        # Assert — single character: original order preserved
        assert refs == [r1, r2, r3]

    def test_project_creation_with_audio_path(self):
        # Arrange & Act
        project = Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters={},
            scenes=[
                Scene(
                    number="1", title="S1", scene_type="still", prompt="P", duration=5
                )
            ],
            audio=Path("audio.m4a"),
        )

        # Assert
        assert project.audio == Path("audio.m4a")

    def test_project_audio_defaults_to_none(self):
        # Arrange & Act
        project = Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters={},
            scenes=[
                Scene(
                    number="1", title="S1", scene_type="still", prompt="P", duration=5
                )
            ],
        )

        # Assert
        assert project.audio is None

    def test_build_prompt_includes_character_descriptions(self):
        """build_prompt should inject character descriptions when scene has characters."""
        # Arrange
        chars = {
            "hero": Character(id="hero", description="A tall boy with red hair"),
            "mum": Character(id="mum", description="A kind woman in a blue dress"),
        }
        scene = Scene(
            number="1",
            title="Meeting",
            scene_type="still",
            prompt="They meet at the gate.",
            duration=5,
            characters=["hero", "mum"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Watercolour.",
            characters=chars,
            scenes=[scene],
        )

        # Act
        prompt = project.build_prompt(scene)

        # Assert — character descriptions are included
        assert "A tall boy with red hair" in prompt
        assert "A kind woman in a blue dress" in prompt
        assert "Watercolour." in prompt
        assert "They meet at the gate." in prompt

    def test_build_prompt_no_characters_unchanged(self):
        """build_prompt without characters should work as before (style + scene prompt)."""
        # Arrange
        scene = Scene(
            number="1",
            title="Empty",
            scene_type="still",
            prompt="A sunset.",
            duration=5,
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Painterly.",
            characters={},
            scenes=[scene],
        )

        # Act
        prompt = project.build_prompt(scene)

        # Assert — no character block, just style + prompt
        assert prompt == "Painterly. A sunset."

    def test_build_prompt_character_not_in_project_is_skipped(self):
        """build_prompt should skip character IDs not found in project.characters."""
        # Arrange
        chars = {
            "hero": Character(id="hero", description="A tall boy"),
        }
        scene = Scene(
            number="1",
            title="Ghost",
            scene_type="still",
            prompt="Walking alone.",
            duration=5,
            characters=["hero", "nonexistent"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="Style.",
            characters=chars,
            scenes=[scene],
        )

        # Act
        prompt = project.build_prompt(scene)

        # Assert — hero included, nonexistent skipped
        assert "A tall boy" in prompt
        assert "nonexistent" not in prompt

    def test_get_reference_images_falls_back_to_characters(self, tmp_path):
        # Arrange — no scene.reference, falls back to character refs
        char_ref = tmp_path / "hero.png"
        char_ref.write_bytes(b"fake")
        chars = {
            "hero": Character(id="hero", description="Hero", reference=[char_ref]),
        }
        scene = Scene(
            number="1",
            title="T",
            scene_type="still",
            prompt="P",
            duration=5,
            characters=["hero"],
        )
        project = Project(
            title="T",
            aspect_ratio="9:16",
            style_prefix="",
            characters=chars,
            scenes=[scene],
        )

        # Act
        refs = project.get_reference_images(scene)

        # Assert — character ref used as fallback
        assert len(refs) == 1
        assert refs[0] == char_ref
