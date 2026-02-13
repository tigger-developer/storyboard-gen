# ABOUTME: Tests for storyboard_gen.cli.
# ABOUTME: Validates command-line argument parsing and subcommand dispatch.

import logging
import os
from pathlib import Path
from unittest.mock import patch

import yaml

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
        assert first_scene.number == 2
        assert second_scene.number == 1

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
        assert mock_gen_still.call_args[0][0].number == 1
        assert mock_gen_clip.call_args[0][0].number == 3


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
        assert ".env" in content
        assert "output/" in content

    def test_init_refuses_if_project_yaml_exists(self, tmp_path, caplog):
        # Arrange
        os.chdir(tmp_path)
        (tmp_path / "project.yaml").write_text("title: Existing")

        # Act
        exit_code = main(["init"])

        # Assert
        assert exit_code == 1
        assert "already exists" in caplog.text

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
