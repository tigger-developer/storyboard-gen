# ABOUTME: Tests for storyboard_gen.assemble.
# ABOUTME: Validates video assembly with and without audio muxing.

from unittest.mock import MagicMock, patch

import pytest

from storyboard_gen.assemble import assemble
from storyboard_gen.models import Project, Scene


def _make_project(scenes=None):
    """Helper to create a minimal project for assembly tests."""
    if scenes is None:
        scenes = [
            Scene(number="1", title="S1", scene_type="still", prompt="P1", duration=5),
            Scene(number="2", title="S2", scene_type="clip", prompt="P2", duration=6),
        ]
    return Project(
        title="Test",
        aspect_ratio="9:16",
        style_prefix="Style.",
        characters={},
        scenes=scenes,
    )


class TestAssembleWithoutAudio:
    def test_assemble_without_audio_uses_copy_concat(self, tmp_path):
        # Arrange — create expected clip files
        project = _make_project()
        intermediate = tmp_path / "intermediate"
        intermediate.mkdir()
        (intermediate / "scene_01.mp4").write_bytes(b"fake-video")
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "scene_02.mp4").write_bytes(b"fake-video")

        with patch("storyboard_gen.assemble.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Act
            assemble(project, tmp_path)

            # Assert — single ffmpeg call with -c copy (no audio muxing)
            assert mock_run.call_count == 1
            cmd = mock_run.call_args[0][0]
            assert "ffmpeg" in cmd
            assert "-c" in cmd
            assert "copy" in cmd

    def test_assemble_raises_for_missing_clip(self, tmp_path):
        # Arrange — no clip files exist
        project = _make_project()

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Missing clip for scene 1"):
            assemble(project, tmp_path)

    def test_assemble_raises_on_ffmpeg_failure(self, tmp_path):
        # Arrange
        project = _make_project()
        intermediate = tmp_path / "intermediate"
        intermediate.mkdir()
        (intermediate / "scene_01.mp4").write_bytes(b"fake-video")
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "scene_02.mp4").write_bytes(b"fake-video")

        with patch("storyboard_gen.assemble.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="encode error")

            # Act & Assert
            with pytest.raises(RuntimeError, match="FFmpeg assembly failed"):
                assemble(project, tmp_path)

    def test_assemble_creates_final_directory(self, tmp_path):
        # Arrange
        project = _make_project()
        intermediate = tmp_path / "intermediate"
        intermediate.mkdir()
        (intermediate / "scene_01.mp4").write_bytes(b"fake-video")
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "scene_02.mp4").write_bytes(b"fake-video")

        with patch("storyboard_gen.assemble.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Act
            assemble(project, tmp_path)

            # Assert
            assert (tmp_path / "final").is_dir()

    def test_assemble_returns_output_path(self, tmp_path):
        # Arrange
        project = _make_project()
        intermediate = tmp_path / "intermediate"
        intermediate.mkdir()
        (intermediate / "scene_01.mp4").write_bytes(b"fake-video")
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "scene_02.mp4").write_bytes(b"fake-video")

        with patch("storyboard_gen.assemble.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Act
            result = assemble(project, tmp_path)

            # Assert
            assert result == tmp_path / "final" / "assembled.mp4"


class TestAssembleWithAudio:
    def test_assemble_with_audio_runs_two_ffmpeg_passes(self, tmp_path):
        # Arrange
        project = _make_project()
        intermediate = tmp_path / "intermediate"
        intermediate.mkdir()
        (intermediate / "scene_01.mp4").write_bytes(b"fake-video")
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "scene_02.mp4").write_bytes(b"fake-video")
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake-audio")

        with patch("storyboard_gen.assemble.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Act
            assemble(project, tmp_path, audio_path=audio_file)

            # Assert — two ffmpeg calls: concat then mux
            assert mock_run.call_count == 2

    def test_assemble_with_audio_uses_shortest_flag(self, tmp_path):
        # Arrange
        project = _make_project()
        intermediate = tmp_path / "intermediate"
        intermediate.mkdir()
        (intermediate / "scene_01.mp4").write_bytes(b"fake-video")
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "scene_02.mp4").write_bytes(b"fake-video")
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake-audio")

        with patch("storyboard_gen.assemble.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Act
            assemble(project, tmp_path, audio_path=audio_file)

            # Assert — second call (mux) contains -shortest
            mux_cmd = mock_run.call_args_list[1][0][0]
            assert "-shortest" in mux_cmd

    def test_assemble_with_audio_cleans_up_temp_files(self, tmp_path):
        # Arrange
        project = _make_project()
        intermediate = tmp_path / "intermediate"
        intermediate.mkdir()
        (intermediate / "scene_01.mp4").write_bytes(b"fake-video")
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "scene_02.mp4").write_bytes(b"fake-video")
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake-audio")

        with patch("storyboard_gen.assemble.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            # Act
            assemble(project, tmp_path, audio_path=audio_file)

            # Assert — no temp concat file left behind in final/
            final_files = list((tmp_path / "final").iterdir())
            temp_files = [f for f in final_files if "concat_only" in f.name]
            assert len(temp_files) == 0

    def test_assemble_with_audio_mux_failure_still_cleans_up(self, tmp_path):
        # Arrange
        project = _make_project()
        intermediate = tmp_path / "intermediate"
        intermediate.mkdir()
        (intermediate / "scene_01.mp4").write_bytes(b"fake-video")
        clips_dir = tmp_path / "clips"
        clips_dir.mkdir()
        (clips_dir / "scene_02.mp4").write_bytes(b"fake-video")
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake-audio")

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MagicMock(returncode=0, stderr="")
            return MagicMock(returncode=1, stderr="mux error")

        with patch("storyboard_gen.assemble.subprocess.run") as mock_run:
            mock_run.side_effect = side_effect

            # Act & Assert
            with pytest.raises(RuntimeError, match="FFmpeg audio mux failed"):
                assemble(project, tmp_path, audio_path=audio_file)

            # Assert — temp file cleaned up despite failure
            final_files = list((tmp_path / "final").iterdir())
            temp_files = [f for f in final_files if "concat_only" in f.name]
            assert len(temp_files) == 0
