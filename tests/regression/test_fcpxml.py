# ABOUTME: Tests for storyboard_gen.fcpxml.
# ABOUTME: Validates FCPXML project generation with Ken Burns transform effects.

import os
import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest
import yaml

from storyboard_gen.config import load_project
from storyboard_gen.fcpxml import (
    _rational_time,
    generate_fcpxml,
)


def _make_project_dir(
    tmp_path, scenes=None, audio=None, subtitles=None, aspect_ratio="9:16"
):
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
        "title": "FCPXML Test",
        "aspect_ratio": aspect_ratio,
        "scenes": scenes,
    }
    if audio:
        data["audio"] = audio
    if subtitles:
        data["subtitles"] = subtitles

    (tmp_path / "project.yaml").write_text(yaml.dump(data))

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


# ---- AC131.1: Valid FCPXML document ----


class TestFcpxmlStructure:
    """AC131.1: FCPXML document validity."""

    @pytest.mark.regression(test_id="RT-001")
    def test_single_still_valid_structure(self, tmp_path):
        """RT-001: Single still scene → valid FCPXML root structure."""
        scenes = [
            {
                "number": 1,
                "title": "Solo",
                "type": "still",
                "duration": 5,
                "prompt": "A scene.",
            },
        ]
        project_dir = _make_project_dir(tmp_path, scenes=scenes)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_fcpxml(project, output_dir)

        # Assert
        assert result.exists()
        assert result.suffix == ".fcpxml"
        tree = ET.parse(result)
        root = tree.getroot()
        assert root.tag == "fcpxml"
        assert root.get("version") == "1.14"
        assert root.find("resources") is not None
        assert root.find("resources/format") is not None
        asset = root.find("resources/asset")
        assert asset is not None
        # src lives on media-rep, not on asset
        assert asset.get("src") is None
        media_rep = asset.find("media-rep")
        assert media_rep is not None
        assert media_rep.get("kind") == "original-media"
        assert media_rep.get("src") is not None
        assert root.find("library") is not None
        assert root.find("library/event") is not None
        assert root.find("library/event/project") is not None
        assert root.find("library/event/project/sequence") is not None
        assert root.find("library/event/project/sequence/spine") is not None

    @pytest.mark.regression(test_id="RT-002")
    def test_single_clip_valid_structure(self, tmp_path):
        """RT-002: Single clip scene → valid FCPXML with video asset."""
        scenes = [
            {
                "number": 1,
                "title": "Action",
                "type": "clip",
                "duration": 6,
                "prompt": "An action.",
            },
        ]
        project_dir = _make_project_dir(tmp_path, scenes=scenes)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_fcpxml(project, output_dir)

        # Assert
        tree = ET.parse(result)
        root = tree.getroot()
        asset = root.find("resources/asset")
        assert asset is not None
        assert asset.get("hasVideo") == "1"
        # Clip assets have non-zero duration
        assert asset.get("duration") != "0s"
        # src on media-rep, not asset
        assert asset.get("src") is None
        media_rep = asset.find("media-rep")
        assert media_rep is not None
        assert media_rep.get("src") is not None

    @pytest.mark.regression(test_id="RT-003")
    def test_multi_scene_mixed_valid(self, tmp_path):
        """RT-003: Multi-scene mixed project → all scenes present."""
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_fcpxml(project, output_dir)

        # Assert
        tree = ET.parse(result)
        root = tree.getroot()
        assets = root.findall("resources/asset")
        assert len(assets) == 3
        spine = root.find("library/event/project/sequence/spine")
        # Stills use <video>, clips use <asset-clip>
        videos = spine.findall("video")
        asset_clips = spine.findall("asset-clip")
        assert len(videos) + len(asset_clips) == 3


# ---- AC131.2: Timeline placement and duration ----


class TestTimelinePlacement:
    """AC131.2: Scene position and duration on timeline."""

    @pytest.mark.regression(test_id="RT-004")
    def test_two_scenes_correct_offsets(self, tmp_path):
        """RT-004: Two scenes with known durations → correct offsets."""
        scenes = [
            {
                "number": 1,
                "title": "First",
                "type": "still",
                "duration": 3,
                "prompt": "A.",
            },
            {
                "number": 2,
                "title": "Second",
                "type": "still",
                "duration": 5,
                "prompt": "B.",
            },
        ]
        project_dir = _make_project_dir(tmp_path, scenes=scenes)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_fcpxml(project, output_dir)

        # Assert
        tree = ET.parse(result)
        spine = tree.find(".//spine")
        # Stills use <video> elements
        clips = spine.findall("video")
        assert clips[0].get("offset") == "0s"
        assert clips[0].get("duration") == _rational_time(3, 30)
        assert clips[1].get("offset") == _rational_time(3, 30)
        assert clips[1].get("duration") == _rational_time(5, 30)

    @pytest.mark.regression(test_id="RT-005")
    def test_non_default_duration_frame_count(self, tmp_path):
        """RT-005: Non-default duration → correct rational time."""
        scenes = [
            {
                "number": 1,
                "title": "Custom",
                "type": "still",
                "duration": 7.5,
                "prompt": "A.",
            },
        ]
        project_dir = _make_project_dir(tmp_path, scenes=scenes)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_fcpxml(project, output_dir)

        # Assert
        tree = ET.parse(result)
        # Still uses <video> element
        clip = tree.find(".//video")
        # 7.5s * 30fps = 225 frames → 225 * 100 / 3000 = 22500/3000s
        assert clip.get("duration") == "22500/3000s"

    @pytest.mark.regression(test_id="RT-006")
    def test_three_scenes_order_matches_yaml(self, tmp_path):
        """RT-006: Three scenes → timeline order matches YAML order."""
        scenes = [
            {
                "number": 1,
                "title": "Alpha",
                "type": "still",
                "duration": 2,
                "prompt": "A.",
            },
            {
                "number": 2,
                "title": "Beta",
                "type": "clip",
                "duration": 3,
                "prompt": "B.",
            },
            {
                "number": 3,
                "title": "Gamma",
                "type": "still",
                "duration": 4,
                "prompt": "C.",
            },
        ]
        project_dir = _make_project_dir(tmp_path, scenes=scenes)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_fcpxml(project, output_dir)

        # Assert
        tree = ET.parse(result)
        spine = tree.find(".//spine")
        # Stills are <video>, clips are <asset-clip> — collect all in order
        clips = list(spine)
        assert [c.get("name") for c in clips] == ["Alpha", "Beta", "Gamma"]


# ---- AC131.3: Ken Burns transforms ----


class TestKenBurnsCrop:
    """AC131.3: Ken Burns effects as FCP-native adjust-crop pan mode."""

    def _get_crop(self, tmp_path, ken_burns):
        """Helper: generate FCPXML with a single still and given ken_burns."""
        scenes = [
            {
                "number": 1,
                "title": "KB Scene",
                "type": "still",
                "duration": 5,
                "ken_burns": ken_burns,
                "prompt": "A scene.",
            },
        ]
        project_dir = _make_project_dir(tmp_path, scenes=scenes)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        result = generate_fcpxml(project, output_dir)
        tree = ET.parse(result)
        clip = tree.find(".//video")
        return clip.find("adjust-crop")

    @pytest.mark.regression(test_id="RT-007")
    def test_zoom_in_start_full_end_cropped(self, tmp_path):
        """RT-007: zoom_in → start full frame, end cropped (zoomed in)."""
        crop = self._get_crop(tmp_path, "zoom_in")
        assert crop is not None
        assert crop.get("mode") == "pan"
        rects = crop.findall("pan-rect")
        assert len(rects) == 2
        # Start: full frame (all zeros)
        assert rects[0].get("left") == "0"
        assert rects[0].get("top") == "0"
        # End: cropped (positive insets)
        assert float(rects[1].get("left")) > 0
        assert float(rects[1].get("top")) > 0

    @pytest.mark.regression(test_id="RT-008")
    def test_zoom_out_start_cropped_end_full(self, tmp_path):
        """RT-008: zoom_out → start cropped (zoomed in), end full frame."""
        crop = self._get_crop(tmp_path, "zoom_out")
        assert crop is not None
        rects = crop.findall("pan-rect")
        # Start: cropped
        assert float(rects[0].get("left")) > 0
        assert float(rects[0].get("top")) > 0
        # End: full frame
        assert rects[1].get("left") == "0"
        assert rects[1].get("top") == "0"

    @pytest.mark.regression(test_id="RT-009")
    def test_pan_ltr_crop_shifts_right(self, tmp_path):
        """RT-009: pan_ltr → start cropped on left, end cropped on right."""
        crop = self._get_crop(tmp_path, "pan_ltr")
        assert crop is not None
        rects = crop.findall("pan-rect")
        # Start: left inset > right inset
        assert float(rects[0].get("left")) > float(rects[0].get("right"))
        # End: right inset > left inset
        assert float(rects[1].get("right")) > float(rects[1].get("left"))

    @pytest.mark.regression(test_id="RT-010")
    def test_pan_rtl_crop_shifts_left(self, tmp_path):
        """RT-010: pan_rtl → start cropped on right, end cropped on left."""
        crop = self._get_crop(tmp_path, "pan_rtl")
        assert crop is not None
        rects = crop.findall("pan-rect")
        # Start: right inset > left inset
        assert float(rects[0].get("right")) > float(rects[0].get("left"))
        # End: left inset > right inset
        assert float(rects[1].get("left")) > float(rects[1].get("right"))

    @pytest.mark.regression(test_id="RT-011")
    def test_static_no_crop(self, tmp_path):
        """RT-011: static or absent ken_burns → no adjust-crop element."""
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        crop = self._get_crop(static_dir, "static")
        assert crop is None
        none_dir = tmp_path / "none"
        none_dir.mkdir()
        crop_none = self._get_crop(none_dir, None)
        assert crop_none is None


# ---- AC131.4: Audio lane ----


class TestAudioLane:
    """AC131.4: Audio inclusion in FCPXML."""

    @pytest.mark.regression(test_id="RT-012")
    def test_audio_path_included(self, tmp_path):
        """RT-012: Audio path provided → audio asset and lane present."""
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        audio_file = tmp_path / "narration.wav"
        audio_file.write_bytes(b"fake-audio")

        # Act
        result = generate_fcpxml(project, output_dir, audio_path=audio_file)

        # Assert
        tree = ET.parse(result)
        root = tree.getroot()
        # Audio-only asset in resources (hasAudio but no hasVideo)
        audio_assets = [
            a
            for a in root.findall("resources/asset")
            if a.get("hasAudio") == "1" and a.get("hasVideo") is None
        ]
        assert len(audio_assets) == 1
        audio_mr = audio_assets[0].find("media-rep")
        assert audio_mr is not None
        assert audio_mr.get("src") is not None
        # Audio element on timeline
        audio_elems = tree.findall(".//audio")
        assert len(audio_elems) >= 1
        assert audio_elems[0].get("lane") == "-1"
        assert audio_elems[0].get("role") == "music.music-1"

    @pytest.mark.regression(test_id="RT-013")
    def test_no_audio_path(self, tmp_path):
        """RT-013: No audio path → no audio in FCPXML."""
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_fcpxml(project, output_dir)

        # Assert
        tree = ET.parse(result)
        root = tree.getroot()
        audio_only_assets = [
            a
            for a in root.findall("resources/asset")
            if a.get("hasAudio") == "1" and a.get("hasVideo") is None
        ]
        assert len(audio_only_assets) == 0
        assert tree.findall(".//audio") == []

    @pytest.mark.regression(test_id="RT-014")
    def test_preview_suppresses_audio(self, tmp_path):
        """RT-014: --preview with audio in project.yaml → no audio."""
        # Audio is handled at CLI/GUI level, not in generate_fcpxml.
        # When preview is set, audio_path=None is passed.
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act — simulate preview by not passing audio
        result = generate_fcpxml(project, output_dir, audio_path=None)

        # Assert
        tree = ET.parse(result)
        assert tree.findall(".//audio") == []


# ---- AC131.5: Subtitles ----


class TestSubtitles:
    """AC131.5: Subtitle data in FCPXML."""

    @pytest.mark.regression(test_id="RT-015")
    def test_subtitles_included(self, tmp_path):
        """RT-015: Subtitles path → title elements present."""
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        srt_file = tmp_path / "subs.srt"
        srt_file.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nHello world\n\n"
            "2\n00:00:04,000 --> 00:00:06,000\nSecond line\n"
        )

        # Act
        result = generate_fcpxml(project, output_dir, subtitles_path=srt_file)

        # Assert
        tree = ET.parse(result)
        titles = tree.findall(".//title")
        assert len(titles) >= 1
        # Check effect resource exists
        effects = tree.findall(".//resources/effect")
        assert len(effects) == 1
        assert effects[0].get("name") == "Basic Title"
        # text-style-def IDs must be unique across the document
        ts_ids = [d.get("id") for d in tree.findall(".//text-style-def")]
        assert len(ts_ids) == len(set(ts_ids)), (
            f"Duplicate text-style-def IDs: {ts_ids}"
        )

    @pytest.mark.regression(test_id="RT-016")
    def test_no_subtitles(self, tmp_path):
        """RT-016: No subtitles path → no title elements."""
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act
        result = generate_fcpxml(project, output_dir)

        # Assert
        tree = ET.parse(result)
        assert tree.findall(".//title") == []
        assert tree.findall(".//resources/effect") == []

    @pytest.mark.regression(test_id="RT-017")
    def test_preview_suppresses_subtitles(self, tmp_path):
        """RT-017: --preview with subtitles → no subtitle data."""
        project_dir = _make_project_dir(tmp_path)
        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"

        # Act — simulate preview by not passing subtitles
        result = generate_fcpxml(project, output_dir, subtitles_path=None)

        # Assert
        tree = ET.parse(result)
        assert tree.findall(".//title") == []


# ---- AC131.6: CLI subcommand ----


class TestCliSubcommand:
    """AC131.6: storyboard-gen fcpxml CLI subcommand."""

    @pytest.mark.regression(test_id="RT-018")
    def test_fcpxml_subcommand_generates_file(self, tmp_path):
        """RT-018: fcpxml subcommand → generates .fcpxml in output/final/."""
        from storyboard_gen.cli import main

        project_dir = _make_project_dir(tmp_path)
        orig = os.getcwd()
        try:
            os.chdir(project_dir)
            result = main(["fcpxml"])
        finally:
            os.chdir(orig)

        # Assert
        assert result == 0
        final_dir = project_dir / "output" / "final"
        fcpxml_files = list(final_dir.glob("*.fcpxml"))
        assert len(fcpxml_files) == 1

    @pytest.mark.regression(test_id="RT-019")
    def test_output_flag_custom_filename(self, tmp_path):
        """RT-019: --output flag → uses specified filename."""
        from storyboard_gen.cli import main

        project_dir = _make_project_dir(tmp_path)
        orig = os.getcwd()
        try:
            os.chdir(project_dir)
            result = main(["fcpxml", "--output", "custom.fcpxml"])
        finally:
            os.chdir(orig)

        # Assert
        assert result == 0
        assert (project_dir / "output" / "final" / "custom.fcpxml").exists()

    @pytest.mark.regression(test_id="RT-020")
    def test_audio_flag_forwarded(self, tmp_path):
        """RT-020: --audio flag → audio path forwarded to generator."""
        from storyboard_gen.cli import main

        project_dir = _make_project_dir(tmp_path)
        audio_file = tmp_path / "music.wav"
        audio_file.write_bytes(b"fake-audio")

        orig = os.getcwd()
        try:
            os.chdir(project_dir)
            with patch(
                "storyboard_gen.cli.generate_fcpxml", wraps=generate_fcpxml
            ) as mock_gen:
                main(["fcpxml", "--audio", str(audio_file)])
                call_kwargs = mock_gen.call_args
                assert call_kwargs[1]["audio_path"] == audio_file.resolve()
        finally:
            os.chdir(orig)

    @pytest.mark.regression(test_id="RT-021")
    def test_subtitles_flag_forwarded(self, tmp_path):
        """RT-021: --subtitles flag → subtitles path forwarded to generator."""
        from storyboard_gen.cli import main

        project_dir = _make_project_dir(tmp_path)
        srt_file = tmp_path / "subs.srt"
        srt_file.write_text("1\n00:00:01,000 --> 00:00:03,000\nHello\n")

        orig = os.getcwd()
        try:
            os.chdir(project_dir)
            with patch(
                "storyboard_gen.cli.generate_fcpxml", wraps=generate_fcpxml
            ) as mock_gen:
                main(["fcpxml", "--subtitles", str(srt_file)])
                call_kwargs = mock_gen.call_args
                assert call_kwargs[1]["subtitles_path"] == srt_file.resolve()
        finally:
            os.chdir(orig)

    @pytest.mark.regression(test_id="RT-022")
    def test_preview_suppresses_audio_and_subtitles(self, tmp_path):
        """RT-022: --preview → audio and subtitles suppressed."""
        from storyboard_gen.cli import main

        project_dir = _make_project_dir(
            tmp_path, audio="music.wav", subtitles="subs.srt"
        )
        # Create the audio and subtitle files referenced in project.yaml
        (project_dir / "music.wav").write_bytes(b"fake")
        (project_dir / "subs.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n")

        orig = os.getcwd()
        try:
            os.chdir(project_dir)
            with patch(
                "storyboard_gen.cli.generate_fcpxml", wraps=generate_fcpxml
            ) as mock_gen:
                main(["fcpxml", "--preview"])
                call_kwargs = mock_gen.call_args
                assert call_kwargs[1]["audio_path"] is None
                assert call_kwargs[1]["subtitles_path"] is None
        finally:
            os.chdir(orig)


# ---- AC131.7: GUI integration ----


class TestGuiIntegration:
    """AC131.7: GUI OutputDialog includes Final Cut Pro option."""

    @pytest.mark.regression(test_id="RT-023")
    def test_output_dialog_has_fcp_radio(self, qtbot):
        """RT-023: OutputDialog contains 'Final Cut Pro' radio button."""
        from storyboard_gen.gui.output_dialog import OutputDialog

        dialog = OutputDialog()
        qtbot.addWidget(dialog)

        assert hasattr(dialog, "_radio_fcpxml")
        assert dialog._radio_fcpxml.text() == "Final Cut Pro export"

    @pytest.mark.regression(test_id="RT-024")
    def test_fcp_mode_returns_fcpxml(self, qtbot):
        """RT-024: Selecting FCP option returns mode='fcpxml'."""
        from storyboard_gen.gui.output_dialog import OutputDialog

        dialog = OutputDialog()
        qtbot.addWidget(dialog)

        dialog._radio_fcpxml.setChecked(True)
        options = dialog.get_options()
        assert options["mode"] == "fcpxml"

    @pytest.mark.regression(test_id="RT-025")
    def test_fcp_mode_updates_extension(self, qtbot):
        """RT-025: Selecting FCP updates filename extension to .fcpxml."""
        from storyboard_gen.gui.output_dialog import OutputDialog

        dialog = OutputDialog(default_title="my_project")
        qtbot.addWidget(dialog)

        # Start with kdenlive (default), switch to fcpxml
        dialog._radio_fcpxml.setChecked(True)
        assert dialog._filename_edit.text().endswith(".fcpxml")


class TestFcpxmlDefaultFilename:
    """AC132.1: CLI fcpxml default filename is snake_case (#132)."""

    @pytest.mark.regression(test_id="RT-031")
    def test_cli_fcpxml_default_filename_snake_case(self, tmp_path):
        """RT-031: CLI fcpxml with multi-word title → snake_case filename."""
        scenes = [
            {
                "number": 1,
                "title": "Opening",
                "type": "still",
                "duration": 5,
                "prompt": "A scene.",
            },
        ]
        project_dir = _make_project_dir(tmp_path, scenes=scenes)
        # Override title to multi-word
        import yaml as _yaml

        data = _yaml.safe_load((project_dir / "project.yaml").read_text())
        data["title"] = "My Great Project"
        (project_dir / "project.yaml").write_text(_yaml.dump(data))

        project = _load_project_from(project_dir)
        output_dir = project_dir / "output"
        result = generate_fcpxml(project, output_dir)

        # Assert — filename is snake_case
        assert result.name == "my_great_project.fcpxml"
