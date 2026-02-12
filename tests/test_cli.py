# ABOUTME: Tests for storyboard_gen.cli.
# ABOUTME: Validates command-line argument parsing and subcommand dispatch.

import os

import pytest

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
