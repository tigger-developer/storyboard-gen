# ABOUTME: Tests for storyboard_gen.cli.
# ABOUTME: Validates command-line argument parsing and subcommand dispatch.

import logging
import os
from pathlib import Path
from unittest.mock import patch

import yaml

import pytest

import storyboard_gen
from storyboard_gen.cli import main


class TestCliValidate:
    def test_validate_succeeds_with_valid_project(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        exit_code = main(["validate"])

        # Assert
        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Test Project" in output
        assert "Valid" in output

    def test_validate_fails_without_project_yaml(self, tmp_path, capsys):
        # Arrange
        os.chdir(tmp_path)

        # Act
        exit_code = main(["validate"])

        # Assert
        assert exit_code == 1


class TestCliList:
    def test_list_shows_all_scenes(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        exit_code = main(["list"])

        # Assert
        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Opening shot" in output
        assert "The meeting" in output
        assert "The chase" in output

    def test_list_shows_total_duration(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        main(["list"])

        # Assert
        output = capsys.readouterr().out
        assert "15s" in output  # 5 + 4 + 6


class TestCliListFloatDurations:
    def test_list_shows_float_durations(self, tmp_path, capsys):
        # Arrange
        data = {
            "title": "Float Test",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 2.5},
                {"number": 2, "type": "still", "prompt": "y", "duration": 3.7},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))
        os.chdir(tmp_path)

        # Act
        exit_code = main(["list"])

        # Assert
        assert exit_code == 0
        output = capsys.readouterr().out
        assert "2.5s" in output
        assert "3.7s" in output
        assert "6.2s" in output  # total

    def test_list_shows_integer_durations_without_decimal(self, tmp_path, capsys):
        # Arrange
        data = {
            "title": "Int Test",
            "scenes": [
                {"number": 1, "type": "still", "prompt": "x", "duration": 5},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))
        os.chdir(tmp_path)

        # Act
        exit_code = main(["list"])

        # Assert
        assert exit_code == 0
        output = capsys.readouterr().out
        assert "5s" in output


class TestCliEnvLoading:
    @patch("storyboard_gen.cli.generate_still")
    def test_generate_loads_dotenv_before_provider_creation(
        self, mock_gen_still, sample_project_dir, monkeypatch
    ):
        # Arrange — put FAL_KEY in .env but not in the environment
        os.chdir(sample_project_dir)
        (sample_project_dir / ".env").write_text("FAL_KEY=test-fal-key-123\n")
        monkeypatch.delenv("FAL_KEY", raising=False)

        # Act
        main(["generate", "--scene", "1"])

        # Assert — FAL_KEY should now be in the environment
        assert os.environ.get("FAL_KEY") == "test-fal-key-123"


class TestCliGenerate:
    @patch("storyboard_gen.cli.generate_still")
    def test_generate_multiple_scenes_in_order(
        self, mock_gen_still, sample_project_dir
    ):
        # Arrange — scenes 2 and 1 (reversed order)
        os.chdir(sample_project_dir)

        # Act
        exit_code = main(["generate", "--scene", "2", "1"])

        # Assert — called in the order specified, not numerical order
        assert exit_code == 0
        assert mock_gen_still.call_count == 2
        first_scene = mock_gen_still.call_args_list[0][0][0]
        second_scene = mock_gen_still.call_args_list[1][0][0]
        assert first_scene.number == "2"
        assert second_scene.number == "1"

    @patch("storyboard_gen.cli.generate_still")
    def test_generate_single_scene_still_works(
        self, mock_gen_still, sample_project_dir
    ):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        exit_code = main(["generate", "--scene", "1"])

        # Assert
        assert exit_code == 0
        mock_gen_still.assert_called_once()

    @patch("storyboard_gen.cli.generate_clip")
    @patch("storyboard_gen.cli.generate_still")
    def test_generate_mixed_still_and_clip_scenes(
        self, mock_gen_still, mock_gen_clip, sample_project_dir
    ):
        # Arrange — scene 1 is still, scene 3 is clip
        os.chdir(sample_project_dir)

        # Act
        exit_code = main(["generate", "--scene", "1", "3"])

        # Assert
        assert exit_code == 0
        mock_gen_still.assert_called_once()
        mock_gen_clip.assert_called_once()
        assert mock_gen_still.call_args[0][0].number == "1"
        assert mock_gen_clip.call_args[0][0].number == "3"


class TestCliInit:
    def test_init_creates_project_yaml_in_current_dir(self, tmp_path, capsys):
        # Arrange
        os.chdir(tmp_path)

        # Act
        exit_code = main(["init"])

        # Assert
        assert exit_code == 0
        project_yaml = tmp_path / "project.yaml"
        assert project_yaml.exists()
        data = yaml.safe_load(project_yaml.read_text())
        assert "title" in data
        assert "scenes" in data
        assert "style_prefix" in data

    def test_init_creates_project_yaml_in_named_dir(self, tmp_path, capsys):
        # Arrange
        target = tmp_path / "my-project"

        # Act
        exit_code = main(["init", str(target)])

        # Assert
        assert exit_code == 0
        assert (target / "project.yaml").exists()

    def test_init_creates_references_directory(self, tmp_path, capsys):
        # Arrange
        os.chdir(tmp_path)

        # Act
        main(["init"])

        # Assert
        assert (tmp_path / "references").is_dir()

    def test_init_creates_logs_directory(self, tmp_path, capsys):
        # Arrange
        os.chdir(tmp_path)

        # Act
        main(["init"])

        # Assert
        assert (tmp_path / "logs").is_dir()

    def test_init_creates_env_file(self, tmp_path, capsys):
        # Arrange
        os.chdir(tmp_path)

        # Act
        main(["init"])

        # Assert
        env_file = tmp_path / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "GOOGLE_CLOUD_PROJECT" in content

    def test_init_creates_gitignore(self, tmp_path, capsys):
        # Arrange
        os.chdir(tmp_path)

        # Act
        main(["init"])

        # Assert
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        # Secrets excluded
        assert ".env" in content
        # Video output excluded
        assert "output/intermediate/" in content
        assert "output/clips/" in content
        # Video formats excluded
        assert "*.mp4" in content
        # Stills kept (NOT excluded)
        assert "!output/stills/" in content
        # Kdenlive project kept (NOT excluded)
        assert "!*.kdenlive" in content

    def test_init_refuses_if_project_yaml_exists(self, tmp_path, caplog):
        # Arrange
        os.chdir(tmp_path)
        (tmp_path / "project.yaml").write_text("title: Existing")

        # Act
        exit_code = main(["init"])

        # Assert
        assert exit_code == 1
        assert "already exists" in caplog.text

    def test_init_creates_readme(self, tmp_path, capsys):
        # Arrange
        os.chdir(tmp_path)

        # Act
        main(["init"])

        # Assert
        readme = tmp_path / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "storyboard-gen" in content
        assert "project.yaml" in content

    def test_init_readme_uses_project_title(self, tmp_path, capsys):
        # Arrange
        os.chdir(tmp_path)

        # Act
        main(["init"])

        # Assert
        readme = tmp_path / "README.md"
        content = readme.read_text()
        # The template project.yaml has title "My Project"
        assert "My Project" in content

    def test_init_prints_summary(self, tmp_path, capsys):
        # Arrange
        os.chdir(tmp_path)

        # Act
        main(["init"])

        # Assert
        output = capsys.readouterr().out
        assert "project.yaml" in output
        assert ".env" in output
        assert ".gitignore" in output
        assert "references/" in output
        assert "logs/" in output
        assert "README.md" in output


class TestCliDryRun:
    def test_dry_run_returns_zero(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        exit_code = main(["generate", "--dry-run", "--all"])

        # Assert
        assert exit_code == 0

    def test_dry_run_shows_prompt(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        main(["generate", "--dry-run", "--scene", "1"])
        output = capsys.readouterr().out

        # Assert — assembled prompt visible (style prefix + camera + scene prompt)
        assert "Watercolour" in output
        assert "A boy stands on a hill" in output

    def test_dry_run_shows_provider(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        main(["generate", "--dry-run", "--scene", "1"])
        output = capsys.readouterr().out

        # Assert — provider backend and model shown
        assert "google" in output
        assert "imagen" in output

    def test_dry_run_shows_camera_phrasing(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        main(["generate", "--dry-run", "--scene", "1"])
        output = capsys.readouterr().out

        # Assert — camera value shown
        assert "WIDE" in output

    def test_dry_run_shows_reference_images(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        main(["generate", "--dry-run", "--scene", "1"])
        output = capsys.readouterr().out

        # Assert — reference image path shown
        assert "hero.png" in output

    @patch("storyboard_gen.cli.generate_still")
    @patch("storyboard_gen.cli.generate_clip")
    def test_dry_run_does_not_call_api(
        self, mock_clip, mock_still, sample_project_dir, capsys
    ):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        main(["generate", "--dry-run", "--all"])

        # Assert — no API calls
        mock_still.assert_not_called()
        mock_clip.assert_not_called()

    def test_dry_run_shows_all_scenes(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        main(["generate", "--dry-run", "--all"])
        output = capsys.readouterr().out

        # Assert — all 3 scenes shown
        assert "Scene 1" in output
        assert "Scene 2" in output
        assert "Scene 3" in output

    def test_dry_run_shows_scene_metadata(self, sample_project_dir, capsys):
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        main(["generate", "--dry-run", "--scene", "1"])
        output = capsys.readouterr().out

        # Assert — type, duration, ken_burns shown
        assert "still" in output
        assert "5" in output
        assert "zoom_in" in output


class TestCliDryRunPricing:
    """Tests for cost estimates in --dry-run output (#80)."""

    def test_dry_run_shows_cost_for_fal_still(self, tmp_path, capsys, monkeypatch):
        """Dry-run shows per-image cost for FAL still scenes."""
        # Arrange
        data = {
            "title": "Pricing Test",
            "providers": {
                "still": {
                    "backend": "fal",
                    "model": "fal-ai/flux-general",
                },
            },
            "scenes": [
                {"number": 1, "type": "still", "duration": 5, "prompt": "x"},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))
        os.chdir(tmp_path)
        monkeypatch.setenv("FAL_KEY", "test-key")

        pricing_data = {"unit_price": 0.04, "unit": "image", "currency": "USD"}
        with patch("storyboard_gen.cli.fetch_price", return_value=pricing_data):
            # Act
            exit_code = main(["generate", "--dry-run", "--all"])
            output = capsys.readouterr().out

        # Assert
        assert exit_code == 0
        assert "$0.04" in output

    def test_dry_run_shows_cost_for_fal_clip(self, tmp_path, capsys, monkeypatch):
        """Dry-run shows duration-based cost for FAL clip scenes."""
        # Arrange
        data = {
            "title": "Pricing Test",
            "providers": {
                "clip": {
                    "backend": "fal",
                    "model": "fal-ai/wan-i2v",
                },
            },
            "scenes": [
                {"number": 1, "type": "clip", "duration": 8, "prompt": "x"},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))
        os.chdir(tmp_path)
        monkeypatch.setenv("FAL_KEY", "test-key")

        pricing_data = {"unit_price": 0.05, "unit": "second", "currency": "USD"}
        with patch("storyboard_gen.cli.fetch_price", return_value=pricing_data):
            # Act
            exit_code = main(["generate", "--dry-run", "--all"])
            output = capsys.readouterr().out

        # Assert
        assert exit_code == 0
        assert "$0.40" in output

    def test_dry_run_shows_unavailable_for_google(self, sample_project_dir, capsys):
        """Dry-run shows 'unavailable' for Google models (no pricing API)."""
        # Arrange
        os.chdir(sample_project_dir)

        with patch("storyboard_gen.cli.fetch_price", return_value=None):
            # Act
            main(["generate", "--dry-run", "--scene", "1"])
            output = capsys.readouterr().out

        # Assert
        assert "unavailable" in output.lower()

    def test_dry_run_shows_total_cost(self, tmp_path, capsys, monkeypatch):
        """Dry-run shows total estimated cost across all scenes."""
        # Arrange
        data = {
            "title": "Total Test",
            "providers": {
                "still": {"backend": "fal", "model": "fal-ai/flux-general"},
            },
            "scenes": [
                {"number": 1, "type": "still", "duration": 5, "prompt": "x"},
                {"number": 2, "type": "still", "duration": 5, "prompt": "y"},
            ],
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))
        os.chdir(tmp_path)
        monkeypatch.setenv("FAL_KEY", "test-key")

        pricing_data = {"unit_price": 0.04, "unit": "image", "currency": "USD"}
        with patch("storyboard_gen.cli.fetch_price", return_value=pricing_data):
            # Act
            main(["generate", "--dry-run", "--all"])
            output = capsys.readouterr().out

        # Assert — total should be $0.08 (2 x $0.04)
        assert "$0.08" in output
        assert "total" in output.lower()


class TestCliSchema:
    def test_schema_subcommand_returns_zero(self, capsys):
        # Arrange & Act
        exit_code = main(["schema"])

        # Assert
        assert exit_code == 0

    def test_schema_includes_top_level_fields(self, capsys):
        # Arrange & Act
        main(["schema"])
        output = capsys.readouterr().out

        # Assert — key top-level fields documented
        assert "title" in output
        assert "aspect_ratio" in output
        assert "style_prefix" in output
        assert "audio" in output

    def test_schema_includes_scene_fields(self, capsys):
        # Arrange & Act
        main(["schema"])
        output = capsys.readouterr().out

        # Assert — key scene fields documented
        assert "duration" in output
        assert "ken_burns" in output
        assert "camera" in output
        assert "characters" in output
        assert "provider" in output

    def test_schema_includes_camera_values(self, capsys):
        # Arrange & Act
        main(["schema"])
        output = capsys.readouterr().out

        # Assert — all 12 camera values listed
        for value in [
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
        ]:
            assert value in output

    def test_schema_includes_ken_burns_values(self, capsys):
        # Arrange & Act
        main(["schema"])
        output = capsys.readouterr().out

        # Assert — ken_burns values listed
        for value in ["zoom_in", "zoom_out", "pan_ltr", "pan_rtl", "static"]:
            assert value in output

    def test_schema_includes_provider_info(self, capsys):
        # Arrange & Act
        main(["schema"])
        output = capsys.readouterr().out

        # Assert — provider backends mentioned
        assert "google" in output
        assert "fal" in output
        assert "replicate" in output


class TestCliAssemble:
    def _make_assemblable_project(self, project_dir, audio=None):
        """Create a project dir with stills and clips ready for assembly."""
        data = {
            "title": "Assemble Test",
            "aspect_ratio": "9:16",
            "scenes": [
                {
                    "number": 1,
                    "type": "still",
                    "duration": 5,
                    "prompt": "A scene.",
                    "ken_burns": "zoom_in",
                },
                {
                    "number": 2,
                    "type": "clip",
                    "duration": 6,
                    "prompt": "Action.",
                },
            ],
        }
        if audio:
            data["audio"] = audio
        (project_dir / "project.yaml").write_text(yaml.dump(data))

        # Create required output files
        output = project_dir / "output"
        stills = output / "stills"
        stills.mkdir(parents=True)
        (stills / "scene_01.png").write_bytes(b"fake-png")
        intermediate = output / "intermediate"
        intermediate.mkdir()
        (intermediate / "scene_01.mp4").write_bytes(b"fake-video")
        clips = output / "clips"
        clips.mkdir()
        (clips / "scene_02.mp4").write_bytes(b"fake-video")

    @patch("storyboard_gen.cli.assemble")
    @patch("storyboard_gen.cli.apply_ken_burns")
    def test_assemble_calls_assemble_with_no_audio_by_default(
        self, mock_kb, mock_assemble, tmp_path
    ):
        # Arrange
        self._make_assemblable_project(tmp_path)
        os.chdir(tmp_path)
        mock_assemble.return_value = Path("output/final/assembled.mp4")

        # Act
        exit_code = main(["assemble"])

        # Assert
        assert exit_code == 0
        mock_assemble.assert_called_once()
        _, kwargs = mock_assemble.call_args
        assert kwargs.get("audio_path") is None

    @patch("storyboard_gen.cli.assemble")
    @patch("storyboard_gen.cli.apply_ken_burns")
    def test_assemble_passes_audio_from_project_yaml(
        self, mock_kb, mock_assemble, tmp_path
    ):
        # Arrange
        self._make_assemblable_project(tmp_path, audio="narration.m4a")
        audio_file = tmp_path / "narration.m4a"
        audio_file.write_bytes(b"fake-audio")
        os.chdir(tmp_path)
        mock_assemble.return_value = Path("output/final/assembled.mp4")

        # Act
        exit_code = main(["assemble"])

        # Assert
        assert exit_code == 0
        _, kwargs = mock_assemble.call_args
        assert kwargs["audio_path"] == audio_file

    @patch("storyboard_gen.cli.assemble")
    @patch("storyboard_gen.cli.apply_ken_burns")
    def test_assemble_cli_audio_overrides_project_yaml(
        self, mock_kb, mock_assemble, tmp_path
    ):
        # Arrange
        self._make_assemblable_project(tmp_path, audio="narration.m4a")
        (tmp_path / "narration.m4a").write_bytes(b"fake-audio")
        override_audio = tmp_path / "override.m4a"
        override_audio.write_bytes(b"fake-audio-override")
        os.chdir(tmp_path)
        mock_assemble.return_value = Path("output/final/assembled.mp4")

        # Act
        exit_code = main(["assemble", "--audio", str(override_audio)])

        # Assert
        assert exit_code == 0
        _, kwargs = mock_assemble.call_args
        assert kwargs["audio_path"] == override_audio

    @patch("storyboard_gen.cli.assemble")
    @patch("storyboard_gen.cli.apply_ken_burns")
    def test_assemble_preview_skips_audio(self, mock_kb, mock_assemble, tmp_path):
        # Arrange
        self._make_assemblable_project(tmp_path, audio="narration.m4a")
        (tmp_path / "narration.m4a").write_bytes(b"fake-audio")
        os.chdir(tmp_path)
        mock_assemble.return_value = Path("output/final/assembled.mp4")

        # Act
        exit_code = main(["assemble", "--preview"])

        # Assert
        assert exit_code == 0
        _, kwargs = mock_assemble.call_args
        assert kwargs.get("audio_path") is None

    @patch("storyboard_gen.cli.assemble")
    @patch("storyboard_gen.cli.apply_ken_burns")
    def test_assemble_warns_when_audio_file_missing(
        self, mock_kb, mock_assemble, tmp_path, caplog
    ):
        # Arrange — audio configured but file doesn't exist
        self._make_assemblable_project(tmp_path, audio="missing.m4a")
        os.chdir(tmp_path)
        mock_assemble.return_value = Path("output/final/assembled.mp4")

        # Act
        with caplog.at_level(logging.WARNING):
            exit_code = main(["assemble"])

        # Assert — proceeds without audio, logs warning
        assert exit_code == 0
        _, kwargs = mock_assemble.call_args
        assert kwargs.get("audio_path") is None
        assert "missing.m4a" in caplog.text


class TestCliVersion:
    def test_version_flag_prints_version(self, capsys):
        # Arrange & Act
        exit_code = main(["--version"])

        # Assert
        assert exit_code == 0
        output = capsys.readouterr().out
        assert storyboard_gen.__version__ in output

    def test_version_short_flag_prints_version(self, capsys):
        # Arrange & Act
        exit_code = main(["-V"])

        # Assert
        assert exit_code == 0
        output = capsys.readouterr().out
        assert storyboard_gen.__version__ in output


class TestExpandSceneArgs:
    """Tests for _expand_scene_args range expansion (#65)."""

    def test_expand_scene_args_single_number(self):
        """A single number passes through unchanged."""
        from storyboard_gen.cli import _expand_scene_args

        # Act
        result = _expand_scene_args(["5"])

        # Assert
        assert result == ["5"]

    def test_expand_scene_args_range(self):
        """A range like '10-15' expands to individual numbers."""
        from storyboard_gen.cli import _expand_scene_args

        # Act
        result = _expand_scene_args(["10-15"])

        # Assert
        assert result == ["10", "11", "12", "13", "14", "15"]

    def test_expand_scene_args_mixed(self):
        """Ranges and individual numbers can be mixed."""
        from storyboard_gen.cli import _expand_scene_args

        # Act
        result = _expand_scene_args(["1", "5", "10-12"])

        # Assert
        assert result == ["1", "5", "10", "11", "12"]

    def test_expand_scene_args_multiple_ranges(self):
        """Multiple ranges expand correctly."""
        from storyboard_gen.cli import _expand_scene_args

        # Act
        result = _expand_scene_args(["1-3", "7-9"])

        # Assert
        assert result == ["1", "2", "3", "7", "8", "9"]

    def test_expand_scene_args_reversed_range_raises(self):
        """A reversed range like '48-10' raises ValueError."""
        from storyboard_gen.cli import _expand_scene_args

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid range '48-10'"):
            _expand_scene_args(["48-10"])

    def test_expand_scene_args_single_element_range(self):
        """A range like '5-5' produces a single element."""
        from storyboard_gen.cli import _expand_scene_args

        # Act
        result = _expand_scene_args(["5-5"])

        # Assert
        assert result == ["5"]

    def test_expand_scene_args_preserves_non_numeric(self):
        """Non-numeric scene identifiers pass through unchanged."""
        from storyboard_gen.cli import _expand_scene_args

        # Act
        result = _expand_scene_args(["1a", "bonus"])

        # Assert
        assert result == ["1a", "bonus"]

    @patch("storyboard_gen.cli.generate_still")
    def test_generate_with_range_resolves_scenes(
        self, mock_gen_still, sample_project_dir
    ):
        """Integration: --scene 1-2 should generate scenes 1 and 2."""
        # Arrange
        os.chdir(sample_project_dir)

        # Act
        exit_code = main(["generate", "--scene", "1-2"])

        # Assert
        assert exit_code == 0
        assert mock_gen_still.call_count == 2
        first_scene = mock_gen_still.call_args_list[0][0][0]
        second_scene = mock_gen_still.call_args_list[1][0][0]
        assert first_scene.number == "1"
        assert second_scene.number == "2"
