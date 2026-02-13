# ABOUTME: Tests for storyboard_gen.kdenlive.
# ABOUTME: Validates Kdenlive MLT XML project generation with dissolve transitions.

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from storyboard_gen.cli import main
from storyboard_gen.kdenlive import (
    _build_mlt,
    _frames,
    _resolve_clip_path,
    generate_kdenlive,
)
from storyboard_gen.config import load_project
from storyboard_gen.ken_burns import ASPECT_DIMENSIONS


def _make_project_dir(tmp_path, scenes=None, audio=None, aspect_ratio="9:16"):
    """Create a project directory with scene output files."""
    if scenes is None:
        scenes = [
            {
                "number": 1,
                "title": "Opening",
                "type": "still",
                "duration": 5,
                "ken_burns": "zoom_in",
                "prompt": "A scene.",
            },
            {
                "number": 2,
                "title": "Middle",
                "type": "still",
                "duration": 4,
                "ken_burns": "static",
                "prompt": "Another scene.",
            },
            {
                "number": 3,
                "title": "Action",
                "type": "clip",
                "duration": 6,
                "prompt": "An action scene.",
            },
        ]

    data = {
        "title": "Kdenlive Test",
        "aspect_ratio": aspect_ratio,
        "scenes": scenes,
    }
    if audio:
        data["audio"] = audio

    (tmp_path / "project.yaml").write_text(yaml.dump(data))

    # Create the output files the module expects
    output = tmp_path / "output"
    (output / "intermediate").mkdir(parents=True)
    (output / "clips").mkdir(parents=True)

    for scene in scenes:
        num = scene["number"]
        if scene["type"] == "still":
            (output / "intermediate" / f"scene_{num:02d}.mp4").write_bytes(
                b"fake-video"
            )
        else:
            (output / "clips" / f"scene_{num:02d}.mp4").write_bytes(b"fake-video")

    return tmp_path


def _load_project_from(project_dir):
    """Load a project from a directory."""
    orig = os.getcwd()
    try:
        os.chdir(project_dir)
        return load_project()
    finally:
        os.chdir(orig)


class TestFrameCalculation:
    def test_frames_whole_seconds(self):
        # Arrange & Act & Assert
        assert _frames(5, 30) == 150

    def test_frames_fractional_seconds(self):
        # Arrange & Act & Assert
        assert _frames(2.5, 30) == 75

    def test_frames_zero_duration(self):
        # Arrange & Act & Assert
        assert _frames(0, 30) == 0


class TestResolveClipPath:
    def test_still_scene_resolves_to_intermediate(self, tmp_path):
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        scene = project.get_scene(1)  # still

        # Act
        result = _resolve_clip_path(scene, output_dir)

        # Assert
        assert result == output_dir / "intermediate" / "scene_01.mp4"

    def test_clip_scene_resolves_to_clips(self, tmp_path):
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        scene = project.get_scene(3)  # clip

        # Act
        result = _resolve_clip_path(scene, output_dir)

        # Assert
        assert result == output_dir / "clips" / "scene_03.mp4"


class TestBuildMlt:
    def _build(self, tmp_path, dissolve_frames=15, audio_path=None, **kwargs):
        """Helper to build an MLT document from a test project."""
        project_dir = _make_project_dir(tmp_path, **kwargs)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        mlt = _build_mlt(project, output_dir, dissolve_frames, 30, audio_path)
        return mlt

    def test_mlt_root_element(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert
        assert mlt.tag == "mlt"

    def test_profile_matches_aspect_ratio(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path, aspect_ratio="16:9")

        # Assert
        profile = mlt.find("profile")
        assert profile is not None
        width, height = ASPECT_DIMENSIONS["16:9"]
        assert profile.get("width") == str(width)
        assert profile.get("height") == str(height)
        assert profile.get("frame_rate_num") == "30"

    def test_producer_per_scene(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — 3 scenes = 3 producers
        producers = mlt.findall("producer")
        assert len(producers) == 3

    def test_producer_paths_absolute(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert
        for producer in mlt.findall("producer"):
            resource = None
            for prop in producer.findall("property"):
                if prop.get("name") == "resource":
                    resource = prop.text
                    break
            assert resource is not None
            assert Path(resource).is_absolute()

    def test_audio_producer_when_audio_configured(self, tmp_path):
        # Arrange
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake-audio")

        # Act
        mlt = self._build(tmp_path, audio_path=audio_file)

        # Assert — look for a producer with an audio resource
        found_audio = False
        for producer in mlt.findall("producer"):
            if producer.get("id") == "audio_producer":
                found_audio = True
                break
        assert found_audio

    def test_no_audio_producer_when_no_audio(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path, audio_path=None)

        # Assert
        for producer in mlt.findall("producer"):
            assert producer.get("id") != "audio_producer"


class TestDissolveLayout:
    def _build_with_dissolves(self, tmp_path, dissolve_frames=15, **kwargs):
        """Build an MLT with dissolves enabled."""
        project_dir = _make_project_dir(tmp_path, **kwargs)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, dissolve_frames, 30, None)

    def test_two_playlists_with_dissolves(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_dissolves(tmp_path)

        # Assert
        playlists = mlt.findall("playlist")
        playlist_ids = [p.get("id") for p in playlists]
        assert "playlist0" in playlist_ids
        assert "playlist1" in playlist_ids

    def test_blank_entries_in_alternating_playlists(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_dissolves(tmp_path)

        # Assert — each playlist should have blanks for the other track's clips
        playlist0 = mlt.find("playlist[@id='playlist0']")
        playlist1 = mlt.find("playlist[@id='playlist1']")
        blanks0 = playlist0.findall("blank")
        blanks1 = playlist1.findall("blank")
        # With 3 clips: playlist0 has clips 1,3 with blanks; playlist1 has clip 2 with blanks
        assert len(blanks0) > 0
        assert len(blanks1) > 0

    def test_transition_count_equals_scene_count_minus_one(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_dissolves(tmp_path)

        # Assert — 3 scenes = 2 dissolves, each dissolve has luma + mix = 4 total
        tractor = mlt.find("tractor")
        transitions = tractor.findall("transition")
        luma_transitions = [
            t for t in transitions if t.get("id", "").startswith("dissolve_")
        ]
        assert len(luma_transitions) == 2  # 3 scenes - 1

    def test_transition_dissolve_length(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_dissolves(tmp_path, dissolve_frames=30)

        # Assert
        tractor = mlt.find("tractor")
        transitions = tractor.findall("transition")
        for t in transitions:
            if t.get("id", "").startswith("dissolve_"):
                length = None
                for prop in t.findall("property"):
                    if prop.get("name") == "length":
                        length = prop.text
                        break
                assert length == "30"

    def test_luma_and_mix_transitions_paired(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_dissolves(tmp_path)

        # Assert — each dissolve has a luma (video) and mix (audio) transition
        tractor = mlt.find("tractor")
        transitions = tractor.findall("transition")
        luma_count = sum(
            1 for t in transitions if t.get("id", "").startswith("dissolve_")
        )
        mix_count = sum(1 for t in transitions if t.get("id", "").startswith("mix_"))
        assert luma_count == mix_count
        assert luma_count == 2  # 3 scenes - 1

    def test_single_scene_no_transitions(self, tmp_path):
        # Arrange
        scenes = [
            {
                "number": 1,
                "title": "Only scene",
                "type": "still",
                "duration": 5,
                "ken_burns": "zoom_in",
                "prompt": "Solo.",
            },
        ]

        # Act
        project_dir = _make_project_dir(tmp_path, scenes=scenes)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        mlt = _build_mlt(project, output_dir, 15, 30, None)

        # Assert — single scene means no transitions
        tractor = mlt.find("tractor")
        transitions = tractor.findall("transition")
        assert len(transitions) == 0


class TestNoDissolveLayout:
    def _build_no_dissolves(self, tmp_path, **kwargs):
        """Build an MLT with dissolve_frames=0 (no transitions)."""
        project_dir = _make_project_dir(tmp_path, **kwargs)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, 0, 30, None)

    def test_single_playlist_when_no_dissolve(self, tmp_path):
        # Arrange & Act
        mlt = self._build_no_dissolves(tmp_path)

        # Assert
        playlists = mlt.findall("playlist")
        assert len(playlists) == 1
        assert playlists[0].get("id") == "playlist0"

    def test_all_clips_on_single_playlist(self, tmp_path):
        # Arrange & Act
        mlt = self._build_no_dissolves(tmp_path)

        # Assert — all 3 scenes on one playlist, no blanks
        playlist = mlt.find("playlist[@id='playlist0']")
        entries = playlist.findall("entry")
        assert len(entries) == 3
        blanks = playlist.findall("blank")
        assert len(blanks) == 0


class TestGenerateKdenlive:
    def test_generates_valid_xml_file(self, tmp_path):
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_kdenlive(project, output_dir)

        # Assert — should parse as valid XML
        ET.parse(result)

    def test_output_path_returned(self, tmp_path):
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_kdenlive(project, output_dir)

        # Assert
        assert isinstance(result, Path)
        assert result.exists()

    def test_default_output_filename(self, tmp_path):
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_kdenlive(project, output_dir)

        # Assert — default filename derived from project title
        assert result.name == "Kdenlive Test.kdenlive"

    def test_custom_output_filename(self, tmp_path):
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_kdenlive(
            project, output_dir, output_filename="custom.kdenlive"
        )

        # Assert
        assert result.name == "custom.kdenlive"

    def test_missing_clip_raises_file_not_found(self, tmp_path):
        # Arrange
        scenes = [
            {
                "number": 1,
                "title": "Missing",
                "type": "still",
                "duration": 5,
                "prompt": "Gone.",
            },
        ]
        data = {
            "title": "Missing Clip Test",
            "aspect_ratio": "9:16",
            "scenes": scenes,
        }
        (tmp_path / "project.yaml").write_text(yaml.dump(data))
        # Do NOT create the output files
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        project = _load_project_from(tmp_path)

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            generate_kdenlive(project, output_dir)


class TestCliKdenlive:
    def test_kdenlive_subcommand_exists(self, tmp_path):
        # Arrange
        _make_project_dir(tmp_path)
        os.chdir(tmp_path)

        # Act
        exit_code = main(["kdenlive"])

        # Assert
        assert exit_code == 0

    def test_dissolve_flag_parsed(self, tmp_path):
        # Arrange
        _make_project_dir(tmp_path)
        os.chdir(tmp_path)

        # Act — should succeed with custom dissolve value
        exit_code = main(["kdenlive", "--dissolve", "30"])

        # Assert
        assert exit_code == 0

    def test_no_dissolve_flag_parsed(self, tmp_path):
        # Arrange
        _make_project_dir(tmp_path)
        os.chdir(tmp_path)

        # Act
        exit_code = main(["kdenlive", "--no-dissolve"])

        # Assert
        assert exit_code == 0

    def test_output_flag_parsed(self, tmp_path):
        # Arrange
        _make_project_dir(tmp_path)
        os.chdir(tmp_path)

        # Act
        exit_code = main(["kdenlive", "--output", "custom.kdenlive"])

        # Assert
        assert exit_code == 0
        assert (tmp_path / "output" / "final" / "custom.kdenlive").exists()
