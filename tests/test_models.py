# ABOUTME: Tests for storyboard_gen.models.
# ABOUTME: Validates Project, Scene, and Character dataclasses.

from pathlib import Path

from storyboard_gen.models import Character, Project, Scene


class TestCharacter:
    def test_character_creation_with_all_fields(self):
        # Arrange & Act
        char = Character(
            id="hero", description="A brave lad", reference=Path("ref.png")
        )

        # Assert
        assert char.id == "hero"
        assert char.description == "A brave lad"
        assert char.reference == Path("ref.png")

    def test_character_creation_without_reference(self):
        # Arrange & Act
        char = Character(id="extra", description="Background character")

        # Assert
        assert char.reference is None

    def test_character_is_frozen(self):
        # Arrange
        char = Character(id="hero", description="test")

        # Act & Assert
        try:
            char.id = "villain"
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass


class TestScene:
    def test_scene_creation_with_defaults(self):
        # Arrange & Act
        scene = Scene(
            number=1, title="Test", scene_type="still", prompt="A thing.", duration=5
        )

        # Assert
        assert scene.number == 1
        assert scene.camera is None
        assert scene.ken_burns is None
        assert scene.characters == []

    def test_scene_creation_with_all_fields(self):
        # Arrange & Act
        scene = Scene(
            number=3,
            title="Action",
            scene_type="clip",
            prompt="Running.",
            duration=8,
            camera="WIDE",
            ken_burns="zoom_in",
            characters=["hero", "sidekick"],
        )

        # Assert
        assert scene.scene_type == "clip"
        assert scene.ken_burns == "zoom_in"
        assert len(scene.characters) == 2


class TestProject:
    def _make_project(self) -> Project:
        """Helper to create a minimal project for testing."""
        chars = {
            "hero": Character(id="hero", description="The hero"),
        }
        scenes = [
            Scene(number=1, title="S1", scene_type="still", prompt="P1", duration=5),
            Scene(number=2, title="S2", scene_type="clip", prompt="P2", duration=6),
            Scene(number=3, title="S3", scene_type="still", prompt="P3", duration=4),
        ]
        return Project(
            title="Test",
            aspect_ratio="9:16",
            style_prefix="Watercolour style.",
            characters=chars,
            scenes=scenes,
        )

    def test_get_scene_returns_correct_scene(self):
        # Arrange
        project = self._make_project()

        # Act
        scene = project.get_scene(2)

        # Assert
        assert scene.title == "S2"

    def test_get_scene_raises_for_missing_number(self):
        # Arrange
        project = self._make_project()

        # Act & Assert
        try:
            project.get_scene(99)
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
        scene = project.get_scene(1)

        # Act
        prompt = project.build_prompt(scene)

        # Assert
        assert prompt.startswith("Watercolour style.")
        assert "P1" in prompt

    def test_get_reference_images_returns_existing_refs(self, tmp_path):
        # Arrange
        ref_path = tmp_path / "hero.png"
        ref_path.write_bytes(b"fake")
        chars = {
            "hero": Character(id="hero", description="Hero", reference=ref_path),
            "ghost": Character(
                id="ghost", description="Ghost", reference=tmp_path / "nope.png"
            ),
        }
        scene = Scene(
            number=1,
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

        # Assert
        assert len(refs) == 1
        assert refs[0] == ref_path
