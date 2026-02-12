# ABOUTME: Tests for storyboard_gen.cli.
# ABOUTME: Validates command-line argument parsing and subcommand dispatch.

import os
from unittest.mock import patch

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
