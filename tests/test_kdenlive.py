# ABOUTME: Tests for storyboard_gen.kdenlive.
# ABOUTME: Validates Kdenlive MLT XML project generation with Ken Burns transform effects.

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from storyboard_gen.cli import main
from storyboard_gen.config import load_project
from storyboard_gen.kdenlive import (
    _build_mlt,
    _frames,
    _probe_audio,
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
    (output / "stills").mkdir(parents=True)
    (output / "clips").mkdir(parents=True)

    for scene in scenes:
        num = str(scene["number"])
        padded = f"{int(num):02d}" if num.isdigit() else num
        if scene["type"] == "still":
            (output / "stills" / f"scene_{padded}.png").write_bytes(b"fake-image")
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
    def test_still_scene_resolves_to_stills_png(self, tmp_path):
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        scene = project.get_scene(1)  # still

        # Act
        result = _resolve_clip_path(scene, output_dir)

        # Assert
        assert result == output_dir / "stills" / "scene_01.png"

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
    def _build(self, tmp_path, audio_path=None, **kwargs):
        """Helper to build an MLT document from a test project."""
        project_dir = _make_project_dir(tmp_path, **kwargs)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        mlt = _build_mlt(project, output_dir, 30, audio_path)
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

    def _build(self, tmp_path, audio_path=None, **kwargs):
        project_dir = _make_project_dir(tmp_path, **kwargs)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, 30, audio_path)

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


class TestVideoTrackLayout:
    def _build(self, tmp_path, **kwargs):
        """Build an MLT document."""
        project_dir = _make_project_dir(tmp_path, **kwargs)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, 30, None)

    def test_single_playlist_has_all_entries(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — playlist0 has entries, playlist1 is empty
        playlist0 = mlt.find("playlist[@id='playlist0']")
        entries = playlist0.findall("entry")
        assert len(entries) == 3

        playlist1 = mlt.find("playlist[@id='playlist1']")
        assert playlist1 is not None
        assert len(playlist1.findall("entry")) == 0

    def test_no_blanks_on_playlist(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path)

        # Assert — sequential clips, no blanks
        playlist = mlt.find("playlist[@id='playlist0']")
        blanks = playlist.findall("blank")
        assert len(blanks) == 0

    def test_producers_have_original_lengths(self, tmp_path):
        # Arrange & Act — scenes: 5s (150f), 4s (120f), 6s (180f) at 30fps
        mlt = self._build(tmp_path)

        # Assert — all producers have original lengths
        p1 = mlt.find("producer[@id='producer_1']")
        assert p1.get("out") == "149"  # 150 - 1

        p2 = mlt.find("producer[@id='producer_2']")
        assert p2.get("out") == "119"  # 120 - 1

        p3 = mlt.find("producer[@id='producer_3']")
        assert p3.get("out") == "179"  # 180 - 1

    def test_timeline_total_equals_sum_of_durations(self, tmp_path):
        # Arrange & Act — 5s + 4s + 6s = 15s = 450 frames at 30fps
        mlt = self._build(tmp_path)

        # Assert — sequence_tractor out attribute = total_frames - 1 = 449
        seq = mlt.find("tractor[@id='sequence_tractor']")
        assert seq.get("out") == "449"


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

    def test_output_flag_parsed(self, tmp_path):
        # Arrange
        _make_project_dir(tmp_path)
        os.chdir(tmp_path)

        # Act
        exit_code = main(["kdenlive", "--output", "custom.kdenlive"])

        # Assert
        assert exit_code == 0
        assert (tmp_path / "output" / "final" / "custom.kdenlive").exists()


class TestKenBurnsFilter:
    """Tests for Ken Burns effects via Kdenlive's native qtblend transform filter."""

    def _build(self, tmp_path, scenes=None, aspect_ratio="9:16"):
        """Build an MLT document from a test project."""
        project_dir = _make_project_dir(
            tmp_path, scenes=scenes, aspect_ratio=aspect_ratio
        )
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, 30, None)

    def _find_producer(self, mlt, scene_number):
        """Find a producer element by scene number."""
        return mlt.find(f"producer[@id='producer_{scene_number}']")

    def _find_transform_filter(self, producer):
        """Find a qtblend transform filter child element of a producer."""
        for f in producer.findall("filter"):
            if _get_prop(f, "mlt_service") == "qtblend":
                return f
        return None

    def test_still_producer_has_loop_property(self, tmp_path):
        # Arrange
        scenes = [
            {
                "number": 1,
                "title": "Still",
                "type": "still",
                "duration": 5,
                "ken_burns": "zoom_in",
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)

        # Assert
        assert _get_prop(producer, "loop") == "1"

    def test_clip_producer_no_loop_property(self, tmp_path):
        # Arrange
        scenes = [
            {
                "number": 1,
                "title": "Clip",
                "type": "clip",
                "duration": 5,
                "prompt": "Action.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)

        # Assert
        assert _get_prop(producer, "loop") is None

    def test_still_zoom_in_has_transform_filter(self, tmp_path):
        # Arrange — 9:16 → 1080x1920, 5s = 150 frames, last frame = 149
        scenes = [
            {
                "number": 1,
                "title": "Zoom In",
                "type": "still",
                "duration": 5,
                "ken_burns": "zoom_in",
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)
        transform = self._find_transform_filter(producer)

        # Assert — start full, end 1.2x centered
        # 1080*1.2=1296, 1920*1.2=2304
        # x_offset=(1080-1296)/2=-108, y_offset=(1920-2304)/2=-192
        assert transform is not None
        rect = _get_prop(transform, "rect")
        assert rect == "0=0 0 1080 1920 1;149=-108 -192 1296 2304 1"

    def test_still_zoom_out_has_transform_filter(self, tmp_path):
        # Arrange
        scenes = [
            {
                "number": 1,
                "title": "Zoom Out",
                "type": "still",
                "duration": 5,
                "ken_burns": "zoom_out",
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)
        transform = self._find_transform_filter(producer)

        # Assert — start 1.2x centered, end full
        assert transform is not None
        rect = _get_prop(transform, "rect")
        assert rect == "0=-108 -192 1296 2304 1;149=0 0 1080 1920 1"

    def test_still_pan_ltr_has_transform_filter(self, tmp_path):
        # Arrange
        scenes = [
            {
                "number": 1,
                "title": "Pan LTR",
                "type": "still",
                "duration": 5,
                "ken_burns": "pan_ltr",
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)
        transform = self._find_transform_filter(producer)

        # Assert — 1.2x scale, pan from left edge to right edge
        # At start: x=0, y centered at -192
        # At end: x=1080-1296=-216, y centered at -192
        assert transform is not None
        rect = _get_prop(transform, "rect")
        assert rect == "0=0 -192 1296 2304 1;149=-216 -192 1296 2304 1"

    def test_still_pan_rtl_has_transform_filter(self, tmp_path):
        # Arrange
        scenes = [
            {
                "number": 1,
                "title": "Pan RTL",
                "type": "still",
                "duration": 5,
                "ken_burns": "pan_rtl",
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)
        transform = self._find_transform_filter(producer)

        # Assert — 1.2x scale, pan from right edge to left edge
        assert transform is not None
        rect = _get_prop(transform, "rect")
        assert rect == "0=-216 -192 1296 2304 1;149=0 -192 1296 2304 1"

    def test_still_static_no_transform_filter(self, tmp_path):
        # Arrange
        scenes = [
            {
                "number": 1,
                "title": "Static",
                "type": "still",
                "duration": 5,
                "ken_burns": "static",
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)
        transform = self._find_transform_filter(producer)

        # Assert — static means no pan/zoom animation
        assert transform is None

    def test_still_no_ken_burns_no_transform_filter(self, tmp_path):
        # Arrange — no ken_burns key at all
        scenes = [
            {
                "number": 1,
                "title": "No KB",
                "type": "still",
                "duration": 5,
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)
        transform = self._find_transform_filter(producer)

        # Assert
        assert transform is None

    def test_clip_no_transform_filter(self, tmp_path):
        # Arrange — clips never get Ken Burns effects
        scenes = [
            {
                "number": 1,
                "title": "Clip",
                "type": "clip",
                "duration": 5,
                "prompt": "Action.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)
        transform = self._find_transform_filter(producer)

        # Assert
        assert transform is None

    def test_transform_filter_has_kdenlive_id(self, tmp_path):
        """Transform filter must have kdenlive_id so Kdenlive shows it in effects panel."""
        # Arrange
        scenes = [
            {
                "number": 1,
                "title": "Zoom In",
                "type": "still",
                "duration": 5,
                "ken_burns": "zoom_in",
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        producer = self._find_producer(mlt, 1)
        transform = self._find_transform_filter(producer)

        # Assert — kdenlive_id is required for Kdenlive GUI recognition
        assert transform is not None
        assert _get_prop(transform, "kdenlive_id") == "qtblend"

    def test_transform_keyframes_16_9_aspect(self, tmp_path):
        # Arrange — 16:9 → 1920x1080
        scenes = [
            {
                "number": 1,
                "title": "Wide Zoom",
                "type": "still",
                "duration": 5,
                "ken_burns": "zoom_in",
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes, aspect_ratio="16:9")
        producer = self._find_producer(mlt, 1)
        transform = self._find_transform_filter(producer)

        # Assert — 1920*1.2=2304, 1080*1.2=1296
        # x_offset=(1920-2304)/2=-192, y_offset=(1080-1296)/2=-108
        assert transform is not None
        rect = _get_prop(transform, "rect")
        assert rect == "0=0 0 1920 1080 1;149=-192 -108 2304 1296 1"


class TestAudioProducer:
    """Tests for audio-specific producer properties in Kdenlive export."""

    def _build_with_audio(self, tmp_path):
        """Build an MLT document with an audio file."""
        audio_file = tmp_path / "audio.m4a"
        audio_file.write_bytes(b"fake-audio")
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, 30, audio_file)

    def test_audio_producer_has_video_index_minus_one(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_audio(tmp_path)
        audio = mlt.find("producer[@id='audio_producer']")

        # Assert — tells MLT not to probe for video in audio-only files
        assert _get_prop(audio, "video_index") == "-1"

    def test_audio_producer_has_audio_index_zero(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_audio(tmp_path)
        audio = mlt.find("producer[@id='audio_producer']")

        # Assert — explicitly selects first audio stream
        assert _get_prop(audio, "audio_index") == "0"

    def test_audio_producer_has_clip_type_audio(self, tmp_path):
        # Arrange & Act
        mlt = self._build_with_audio(tmp_path)
        audio = mlt.find("producer[@id='audio_producer']")

        # Assert — Kdenlive audio clip classification
        assert _get_prop(audio, "kdenlive:clip_type") == "1"

    def test_scene_producers_no_audio_properties(self, tmp_path):
        # Arrange & Act — scene producers should NOT have audio-only properties
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        mlt = _build_mlt(project, output_dir, 30, None)

        # Assert
        for producer in mlt.findall("producer"):
            pid = producer.get("id")
            if pid == "black_track":
                continue
            assert _get_prop(producer, "video_index") is None
            assert _get_prop(producer, "kdenlive:clip_type") is None


class TestZeroDurationScene:
    """Tests for scenes with duration: 0 (e.g. pre-roll title cards).

    Fixes #40: 0-duration scenes produce out="-1" in playlist entries,
    which MLT interprets as natural duration (~30s for stills).
    """

    def _build(self, tmp_path, scenes=None):
        """Build an MLT document from a test project."""
        project_dir = _make_project_dir(tmp_path, scenes=scenes)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, 30, None)

    def test_zero_duration_scene_excluded_from_playlist(self, tmp_path):
        """A scene with duration 0 must not appear in playlist0 entries."""
        # Arrange — scene 0 has 0 duration, scene 1 has 5s
        scenes = [
            {
                "number": 0,
                "title": "Pre-roll",
                "type": "still",
                "duration": 0,
                "prompt": "Title card.",
            },
            {
                "number": 1,
                "title": "Opening",
                "type": "still",
                "duration": 5,
                "ken_burns": "zoom_in",
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        playlist0 = mlt.find("playlist[@id='playlist0']")
        entries = playlist0.findall("entry")

        # Assert — only scene 1 should be on the timeline
        entry_producers = [e.get("producer") for e in entries]
        assert "producer_0" not in entry_producers
        assert "producer_1" in entry_producers
        assert len(entries) == 1

    def test_zero_duration_scene_still_in_main_bin(self, tmp_path):
        """A scene with duration 0 should still be registered in main_bin."""
        # Arrange
        scenes = [
            {
                "number": 0,
                "title": "Pre-roll",
                "type": "still",
                "duration": 0,
                "prompt": "Title card.",
            },
            {
                "number": 1,
                "title": "Opening",
                "type": "still",
                "duration": 5,
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        main_bin = mlt.find("playlist[@id='main_bin']")
        entry_producers = [e.get("producer") for e in main_bin.findall("entry")]

        # Assert — both producers registered in main_bin
        assert "producer_0" in entry_producers
        assert "producer_1" in entry_producers

    def test_zero_duration_scene_producer_still_created(self, tmp_path):
        """A scene with duration 0 should still have a producer element."""
        # Arrange
        scenes = [
            {
                "number": 0,
                "title": "Pre-roll",
                "type": "still",
                "duration": 0,
                "prompt": "Title card.",
            },
            {
                "number": 1,
                "title": "Opening",
                "type": "still",
                "duration": 5,
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)

        # Assert — producer element exists even though it's not on the timeline
        producer_0 = mlt.find("producer[@id='producer_0']")
        assert producer_0 is not None
        assert _get_prop(producer_0, "kdenlive:clipname") == "Pre-roll"

    def test_zero_duration_excluded_from_timeline_total(self, tmp_path):
        """Timeline total frames should not include 0-duration scenes."""
        # Arrange — scene 0 (0s) + scene 1 (5s) = 150 frames at 30fps
        scenes = [
            {
                "number": 0,
                "title": "Pre-roll",
                "type": "still",
                "duration": 0,
                "prompt": "Title card.",
            },
            {
                "number": 1,
                "title": "Opening",
                "type": "still",
                "duration": 5,
                "prompt": "A scene.",
            },
        ]

        # Act
        mlt = self._build(tmp_path, scenes=scenes)
        seq = mlt.find("tractor[@id='sequence_tractor']")

        # Assert — total = 150 frames, out = 149
        assert seq.get("out") == "149"


class TestSubtitleTrack:
    """Tests for Kdenlive native subtitle track support (#84, #89)."""

    def _build(self, tmp_path, subtitles_path=None, **kwargs):
        """Build an MLT document from a test project, optionally with subtitles."""
        project_dir = _make_project_dir(tmp_path, **kwargs)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        return _build_mlt(project, output_dir, 30, None, subtitles_path=subtitles_path)

    def test_subtitle_filter_present_when_subtitles_configured(self, tmp_path):
        # Arrange
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

        # Act
        mlt = self._build(tmp_path, subtitles_path=srt_file)

        # Assert
        seq = mlt.find("tractor[@id='sequence_tractor']")
        filters = seq.findall("filter")
        sub_filters = [
            f for f in filters if _get_prop(f, "mlt_service") == "avfilter.subtitles"
        ]
        assert len(sub_filters) == 1

    def test_subtitle_filter_absent_when_no_subtitles(self, tmp_path):
        # Arrange & Act
        mlt = self._build(tmp_path, subtitles_path=None)

        # Assert
        seq = mlt.find("tractor[@id='sequence_tractor']")
        filters = seq.findall("filter")
        sub_filters = [
            f for f in filters if _get_prop(f, "mlt_service") == "avfilter.subtitles"
        ]
        assert len(sub_filters) == 0

    def test_subtitle_filter_has_correct_mlt_service(self, tmp_path):
        # Arrange
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

        # Act
        mlt = self._build(tmp_path, subtitles_path=srt_file)

        # Assert
        seq = mlt.find("tractor[@id='sequence_tractor']")
        filt = seq.find("filter[@id='subtitle_filter']")
        assert _get_prop(filt, "mlt_service") == "avfilter.subtitles"

    def test_subtitle_filter_has_internal_added(self, tmp_path):
        """Kdenlive's native subtitle filter uses internal_added=237 (#89)."""
        # Arrange
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

        # Act
        mlt = self._build(tmp_path, subtitles_path=srt_file)

        # Assert
        seq = mlt.find("tractor[@id='sequence_tractor']")
        filt = seq.find("filter[@id='subtitle_filter']")
        assert _get_prop(filt, "internal_added") == "237"

    def test_subtitle_filter_has_alpha(self, tmp_path):
        """Subtitle filter should have av.alpha=1 for full opacity (#89)."""
        # Arrange
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

        # Act
        mlt = self._build(tmp_path, subtitles_path=srt_file)

        # Assert
        seq = mlt.find("tractor[@id='sequence_tractor']")
        filt = seq.find("filter[@id='subtitle_filter']")
        assert _get_prop(filt, "av.alpha") == "1"

    def test_subtitle_filter_filename_is_ass(self, tmp_path):
        """Subtitle filter av.filename should reference the ASS file, not the input (#89)."""
        # Arrange — _build_mlt always receives a pre-converted ASS path
        ass_file = tmp_path / "test.ass"
        ass_file.write_text(
            "[Script Info]\n\n[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Hello\n"
        )

        # Act
        mlt = self._build(tmp_path, subtitles_path=ass_file)

        # Assert
        seq = mlt.find("tractor[@id='sequence_tractor']")
        filt = seq.find("filter[@id='subtitle_filter']")
        filename = _get_prop(filt, "av.filename")
        assert filename.endswith(".ass")

    def test_subtitle_filter_is_child_of_sequence_tractor(self, tmp_path):
        # Arrange
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

        # Act
        mlt = self._build(tmp_path, subtitles_path=srt_file)

        # Assert — filter should be directly on the sequence tractor, not elsewhere
        seq = mlt.find("tractor[@id='sequence_tractor']")
        filt = seq.find("filter[@id='subtitle_filter']")
        assert filt is not None

        # No subtitle filter on video_tractor or other tractors
        video_tractor = mlt.find("tractor[@id='video_tractor']")
        assert video_tractor.find("filter[@id='subtitle_filter']") is None

    def test_ass_file_written_alongside_kdenlive_project(self, tmp_path):
        """generate_kdenlive() writes ASS subtitle file to {output}.kdenlive.ass (#89)."""
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        srt_file = tmp_path / "subs.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        # Act
        result = generate_kdenlive(project, output_dir, subtitles_path=srt_file)

        # Assert — ASS file alongside the .kdenlive
        expected_ass = Path(str(result) + ".ass")
        assert expected_ass.exists()
        content = expected_ass.read_text()
        assert "[Script Info]" in content
        assert "Dialogue:" in content
        assert "Hello" in content

    def test_subtitles_list_property_present(self, tmp_path):
        """Sequence tractor must have subtitlesList JSON property (#89)."""
        # Arrange — _build_mlt always receives a pre-converted ASS path
        ass_file = tmp_path / "test.ass"
        ass_file.write_text(
            "[Script Info]\n\n[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Hello\n"
        )

        # Act
        mlt = self._build(tmp_path, subtitles_path=ass_file)

        # Assert
        seq = mlt.find("tractor[@id='sequence_tractor']")
        subs_list_raw = _get_prop(seq, "kdenlive:sequenceproperties.subtitlesList")
        assert subs_list_raw is not None
        import json

        subs_list = json.loads(subs_list_raw)
        assert len(subs_list) == 1
        assert subs_list[0]["id"] == 0
        assert subs_list[0]["name"] == "Subtitles"
        assert subs_list[0]["file"].endswith(".ass")

    def test_hide_subtitle_property(self, tmp_path):
        """Sequence tractor must have hidesubtitle=0 when subtitles present (#89)."""
        # Arrange
        srt_file = tmp_path / "test.srt"
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")

        # Act
        mlt = self._build(tmp_path, subtitles_path=srt_file)

        # Assert
        seq = mlt.find("tractor[@id='sequence_tractor']")
        assert _get_prop(seq, "kdenlive:sequenceproperties.hidesubtitle") == "0"

    def test_no_subtitle_properties_when_no_subtitles(self, tmp_path):
        """No subtitle properties when subtitles_path is None."""
        # Arrange & Act
        mlt = self._build(tmp_path, subtitles_path=None)

        # Assert
        seq = mlt.find("tractor[@id='sequence_tractor']")
        assert _get_prop(seq, "kdenlive:sequenceproperties.subtitlesList") is None

    def test_vtt_input_generates_ass_output(self, tmp_path):
        """VTT input should be converted to ASS for Kdenlive (#89)."""
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        vtt_file = tmp_path / "subs.vtt"
        vtt_file.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello VTT\n")

        # Act
        result = generate_kdenlive(project, output_dir, subtitles_path=vtt_file)

        # Assert
        expected_ass = Path(str(result) + ".ass")
        assert expected_ass.exists()
        content = expected_ass.read_text()
        assert "Hello VTT" in content

    def test_ass_input_copied_directly(self, tmp_path):
        """ASS input should be copied directly without re-conversion (#89)."""
        # Arrange
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        ass_content = (
            "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello ASS\n"
        )
        ass_file = tmp_path / "subs.ass"
        ass_file.write_text(ass_content)

        # Act
        result = generate_kdenlive(project, output_dir, subtitles_path=ass_file)

        # Assert — ASS copied directly, preserving original content
        expected_ass = Path(str(result) + ".ass")
        assert expected_ass.exists()
        assert expected_ass.read_text() == ass_content


class TestProbeAudio:
    """Tests for ffprobe audio metadata probing."""

    def test_probe_returns_metadata_on_success(self, tmp_path):
        # Arrange
        audio_file = tmp_path / "test.m4a"
        audio_file.write_bytes(b"fake")
        fake_output = json.dumps(
            {
                "streams": [
                    {
                        "sample_rate": "44100",
                        "channels": 1,
                        "codec_name": "aac",
                    }
                ]
            }
        )

        # Act
        with patch("storyboard_gen.kdenlive.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = fake_output
            result = _probe_audio(audio_file)

        # Assert
        assert result == {"sample_rate": "44100", "channels": 1, "codec_name": "aac"}

    def test_probe_returns_none_when_ffprobe_missing(self, tmp_path):
        # Arrange
        audio_file = tmp_path / "test.m4a"
        audio_file.write_bytes(b"fake")

        # Act
        with patch(
            "storyboard_gen.kdenlive.subprocess.run", side_effect=FileNotFoundError
        ):
            result = _probe_audio(audio_file)

        # Assert
        assert result is None

    def test_probe_returns_none_on_nonzero_exit(self, tmp_path):
        # Arrange
        audio_file = tmp_path / "test.m4a"
        audio_file.write_bytes(b"fake")

        # Act
        with patch("storyboard_gen.kdenlive.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            result = _probe_audio(audio_file)

        # Assert
        assert result is None

    def test_probe_returns_none_on_timeout(self, tmp_path):
        # Arrange
        audio_file = tmp_path / "test.m4a"
        audio_file.write_bytes(b"fake")

        # Act
        with patch(
            "storyboard_gen.kdenlive.subprocess.run",
            side_effect=__import__("subprocess").TimeoutExpired("ffprobe", 10),
        ):
            result = _probe_audio(audio_file)

        # Assert
        assert result is None

    def test_probe_returns_none_on_empty_streams(self, tmp_path):
        # Arrange
        audio_file = tmp_path / "test.m4a"
        audio_file.write_bytes(b"fake")

        # Act
        with patch("storyboard_gen.kdenlive.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = json.dumps({"streams": []})
            result = _probe_audio(audio_file)

        # Assert
        assert result is None
