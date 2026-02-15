# ABOUTME: Tests for storyboard_gen.kdenlive.
# ABOUTME: Validates Kdenlive MLT XML project generation with dissolve transitions.

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from storyboard_gen.cli import main
from storyboard_gen.config import load_project
from storyboard_gen.kdenlive import (
    _build_mlt,
    _frames,
    _resolve_clip_path,
    generate_kdenlive,
)
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
        num = str(scene["number"])
        padded = f"{int(num):02d}" if num.isdigit() else num
        if scene["type"] == "still":
            (output / "intermediate" / f"scene_{padded}.mp4").write_bytes(
                b"fake-video"
            )
        else:
            (output / "clips" / f"scene_{padded}.mp4").write_bytes(b"fake-video")

    return tmp_path


def _load_project_from(project_dir):
    """Load a project from a directory."""
    orig = os.getcwd()
    try:
        os.chdir(project_dir)
        return load_project()
    finally:
        os.chdir(orig)


def _get_prop(element, name):
    """Get the text of a <property name="..."> child element."""
    for prop in element.findall("property"):
        if prop.get("name") == name:
            return prop.text
    return None


class TestFrameCalculation:
    def test_frames_whole_seconds(self):
        # Arrange & Act & Assert
        assert _frames(5, 30) == 150

    def test_frames_fractional_seconds(self):
        # Arrange & Act & Assert
        assert _frames(2.5, 30) == 75

    def test_frames_rounds_rather_than_truncates(self):
        # 2.517 * 30 = 75.51 → round() gives 76, int() gives 75
        assert _frames(2.517, 30) == 76

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
        assert mlt.get("producer") == "main_bin"

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

        # Assert — 3 scenes + 1 black_track = 4 producers
        producers = mlt.findall("producer")
        scene_producers = [p for p in producers if _get_prop(p, "resource") != "black"]
        assert len(scene_producers) == 3

    def test_producer_paths_absolute(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — scene producers have absolute paths
        for producer in mlt.findall("producer"):
            resource = _get_prop(producer, "resource")
            if resource == "black":
                continue
            assert resource is not None
            assert Path(resource).is_absolute()

    def test_audio_producer_when_audio_configured(self, tmp_path):
        # Arrange
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake-audio")

        # Act
        mlt = self._build(tmp_path, audio_path=audio_file)

        # Assert
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


class TestKdenliveStructure:
    """Kdenlive-specific structural requirements."""

    def _build(self, tmp_path, dissolve_frames=15, audio_path=None, **kwargs):
        project_dir = _make_project_dir(tmp_path, **kwargs)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, dissolve_frames, 30, audio_path)

    def test_black_track_producer_present(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert
        black = mlt.find("producer[@id='black_track']")
        assert black is not None
        assert _get_prop(black, "resource") == "black"
        assert _get_prop(black, "mlt_service") == "color"

    def test_producers_have_kdenlive_id(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — each scene producer has a kdenlive:id
        for producer in mlt.findall("producer"):
            if producer.get("id") == "black_track":
                continue
            kid = _get_prop(producer, "kdenlive:id")
            assert kid is not None

    def test_producers_have_kdenlive_clipname(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — scene producers have clipname
        for producer in mlt.findall("producer"):
            if producer.get("id") == "black_track":
                continue
            clipname = _get_prop(producer, "kdenlive:clipname")
            assert clipname is not None

    def test_main_bin_present(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert
        main_bin = mlt.find("playlist[@id='main_bin']")
        assert main_bin is not None

    def test_main_bin_contains_all_scene_producers(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — main_bin has entries for all 3 scene producers
        main_bin = mlt.find("playlist[@id='main_bin']")
        entries = main_bin.findall("entry")
        entry_producers = [e.get("producer") for e in entries]
        assert "producer_1" in entry_producers
        assert "producer_2" in entry_producers
        assert "producer_3" in entry_producers

    def test_main_bin_contains_audio_producer(self, tmp_path):
        # Arrange
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake-audio")

        # Act
        mlt = self._build(tmp_path, audio_path=audio_file)

        # Assert
        main_bin = mlt.find("playlist[@id='main_bin']")
        entry_producers = [e.get("producer") for e in main_bin.findall("entry")]
        assert "audio_producer" in entry_producers

    def test_main_bin_has_docproperties_version(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert
        main_bin = mlt.find("playlist[@id='main_bin']")
        version = _get_prop(main_bin, "kdenlive:docproperties.version")
        assert version == "1.1"

    def test_project_tractor_present(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — last tractor should have kdenlive:projectTractor
        tractors = mlt.findall("tractor")
        project_tractors = [
            t for t in tractors if _get_prop(t, "kdenlive:projectTractor") == "1"
        ]
        assert len(project_tractors) == 1

    def test_video_tractor_has_internal_qtblend(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — video_tractor must have an always-active qtblend
        # so that blanks on the top playlist are transparent, letting
        # the bottom playlist's content show through
        video_tractor = mlt.find("tractor[@id='video_tractor']")
        transitions = video_tractor.findall("transition")
        qtblend = [
            t
            for t in transitions
            if _get_prop(t, "mlt_service") == "qtblend"
            and _get_prop(t, "always_active") == "1"
        ]
        assert len(qtblend) == 1
        assert _get_prop(qtblend[0], "a_track") == "0"
        assert _get_prop(qtblend[0], "b_track") == "1"

    def test_video_tractor_has_internal_mix(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — video_tractor must have an always-active mix
        video_tractor = mlt.find("tractor[@id='video_tractor']")
        transitions = video_tractor.findall("transition")
        mix = [
            t
            for t in transitions
            if _get_prop(t, "mlt_service") == "mix"
            and _get_prop(t, "always_active") == "1"
        ]
        assert len(mix) == 1

    def test_playlist_entries_have_kdenlive_id(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — entries in video playlists have kdenlive:id sub-properties
        playlist0 = mlt.find("playlist[@id='playlist0']")
        entries = playlist0.findall("entry")
        assert len(entries) > 0
        for entry in entries:
            kid = _get_prop(entry, "kdenlive:id")
            assert kid is not None


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
        assert len(blanks0) > 0
        assert len(blanks1) > 0

    def test_transition_count_equals_scene_count_minus_one(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_dissolves(tmp_path)

        # Assert — dissolve transitions live inside the video track tractor
        video_tractor = mlt.find("tractor[@id='video_tractor']")
        transitions = video_tractor.findall("transition")
        luma_transitions = [
            t for t in transitions if t.get("id", "").startswith("dissolve_")
        ]
        assert len(luma_transitions) == 2  # 3 scenes - 1

    def test_transition_dissolve_length(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_dissolves(tmp_path, dissolve_frames=30)

        # Assert
        video_tractor = mlt.find("tractor[@id='video_tractor']")
        transitions = video_tractor.findall("transition")
        for t in transitions:
            if t.get("id", "").startswith("dissolve_"):
                length = _get_prop(t, "length")
                assert length == "30"

    def test_luma_and_mix_transitions_paired(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_dissolves(tmp_path)

        # Assert
        video_tractor = mlt.find("tractor[@id='video_tractor']")
        transitions = video_tractor.findall("transition")
        luma_count = sum(
            1 for t in transitions if t.get("id", "").startswith("dissolve_")
        )
        mix_count = sum(1 for t in transitions if t.get("id", "").startswith("mix_"))
        assert luma_count == mix_count
        assert luma_count == 2  # 3 scenes - 1

    def test_dissolve_direction_outgoing_to_incoming(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_dissolves(tmp_path)

        # Assert — dissolve_0 goes from scene 1 (track 0) to scene 2 (track 1)
        # a_track = outgoing clip's track, b_track = incoming clip's track
        video_tractor = mlt.find("tractor[@id='video_tractor']")

        dissolve_0 = video_tractor.find("transition[@id='dissolve_0']")
        assert dissolve_0 is not None
        # Scene 1 on playlist0 (track 0), scene 2 on playlist1 (track 1)
        assert _get_prop(dissolve_0, "a_track") == "0"
        assert _get_prop(dissolve_0, "b_track") == "1"

        dissolve_1 = video_tractor.find("transition[@id='dissolve_1']")
        assert dissolve_1 is not None
        # Scene 2 on playlist1 (track 1), scene 3 on playlist0 (track 0)
        assert _get_prop(dissolve_1, "a_track") == "1"
        assert _get_prop(dissolve_1, "b_track") == "0"

    def test_timeline_total_equals_sum_of_durations_with_dissolves(self, tmp_path):
        # Arrange — 3 scenes: 5s + 4s + 6s = 15s = 450 frames at 30fps
        # With dissolves, the total should STILL be 450 frames because
        # non-first clips are extended to compensate for overlap
        mlt = self._build_with_dissolves(tmp_path, dissolve_frames=15)

        # Assert — sequence_tractor out attribute = total_frames - 1 = 449
        seq = mlt.find("tractor[@id='sequence_tractor']")
        assert seq.get("out") == "449"

    def test_non_first_producers_extended_by_dissolve_frames(self, tmp_path):
        # Arrange — scenes: 5s (150f), 4s (120f), 6s (180f) at 30fps
        # With 15-frame dissolves, producers 2 and 3 should be extended by 15
        mlt = self._build_with_dissolves(tmp_path, dissolve_frames=15)

        # Assert — first producer unchanged, others extended
        p1 = mlt.find("producer[@id='producer_1']")
        assert p1.get("out") == "149"  # 150 - 1 (no extension)

        p2 = mlt.find("producer[@id='producer_2']")
        assert p2.get("out") == "134"  # 120 + 15 - 1 (extended)

        p3 = mlt.find("producer[@id='producer_3']")
        assert p3.get("out") == "194"  # 180 + 15 - 1 (extended)

    def test_playlist_entries_use_extended_lengths(self, tmp_path):
        # Arrange
        mlt = self._build_with_dissolves(tmp_path, dissolve_frames=15)

        # Assert — playlist entries for non-first clips use extended out values
        playlist1 = mlt.find("playlist[@id='playlist1']")
        entries = playlist1.findall("entry")
        # Scene 2 is on playlist1, extended by 15 frames
        scene2_entry = entries[0]
        assert scene2_entry.get("out") == "134"  # 120 + 15 - 1

    def test_no_extension_without_dissolves(self, tmp_path):
        # Arrange — dissolve_frames=0 means no extension
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        mlt = _build_mlt(project, output_dir, 0, 30, None)

        # Assert — all producers have original lengths
        p2 = mlt.find("producer[@id='producer_2']")
        assert p2.get("out") == "119"  # 120 - 1 (no extension)

        # Total timeline = sum of durations = 450 frames
        seq = mlt.find("tractor[@id='sequence_tractor']")
        assert seq.get("out") == "449"

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

        # Assert — single scene: no dissolve transitions in video tractor
        video_tractor = mlt.find("tractor[@id='video_tractor']")
        transitions = video_tractor.findall("transition")
        dissolve_transitions = [
            t for t in transitions if t.get("id", "").startswith("dissolve_")
        ]
        assert len(dissolve_transitions) == 0


class TestNoDissolveLayout:
    def _build_no_dissolves(self, tmp_path, **kwargs):
        """Build an MLT with dissolve_frames=0 (no transitions)."""
        project_dir = _make_project_dir(tmp_path, **kwargs)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, 0, 30, None)

    def test_single_playlist_has_content_when_no_dissolve(self, tmp_path):
        # Arrange & Act
        mlt = self._build_no_dissolves(tmp_path)

        # Assert — playlist0 has entries, playlist1 is empty
        playlist0 = mlt.find("playlist[@id='playlist0']")
        entries = playlist0.findall("entry")
        assert len(entries) == 3

        playlist1 = mlt.find("playlist[@id='playlist1']")
        assert playlist1 is not None
        assert len(playlist1.findall("entry")) == 0

    def test_all_clips_on_single_playlist(self, tmp_path):
        # Arrange & Act
        mlt = self._build_no_dissolves(tmp_path)

        # Assert — all 3 scenes on playlist0, no blanks
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
