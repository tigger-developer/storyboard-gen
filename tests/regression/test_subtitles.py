# ABOUTME: Tests for multi-format subtitle parsing and ASS conversion.
# ABOUTME: Covers SRT, VTT, ASS input parsing and Kdenlive ASS output generation.

import pytest

from storyboard_gen.srt import Subtitle


class TestParseSubtitleFile:
    """Tests for auto-detecting subtitle format by extension."""

    def test_parse_srt_file(self, tmp_path):
        from storyboard_gen.subtitles import parse_subtitle_file

        srt = tmp_path / "subs.srt"
        srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n")

        result = parse_subtitle_file(srt)

        assert len(result) == 1
        assert result[0].text == "Hello"
        assert result[0].start_ms == 1000
        assert result[0].end_ms == 2000

    def test_parse_vtt_file(self, tmp_path):
        from storyboard_gen.subtitles import parse_subtitle_file

        vtt = tmp_path / "subs.vtt"
        vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n")

        result = parse_subtitle_file(vtt)

        assert len(result) == 1
        assert result[0].text == "Hello"
        assert result[0].start_ms == 1000
        assert result[0].end_ms == 2000

    def test_parse_ass_file(self, tmp_path):
        from storyboard_gen.subtitles import parse_subtitle_file

        ass = tmp_path / "subs.ass"
        ass.write_text(
            "[Script Info]\nScriptType: v4.00+\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n"
        )

        result = parse_subtitle_file(ass)

        assert len(result) == 1
        assert result[0].text == "Hello"
        assert result[0].start_ms == 1000
        assert result[0].end_ms == 2000

    def test_parse_ssa_file(self, tmp_path):
        """SSA (v4) format should also be accepted."""
        from storyboard_gen.subtitles import parse_subtitle_file

        ssa = tmp_path / "subs.ssa"
        ssa.write_text(
            "[Script Info]\nScriptType: v4.00\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n"
        )

        result = parse_subtitle_file(ssa)

        assert len(result) == 1
        assert result[0].text == "Hello"

    def test_parse_unknown_extension_raises(self, tmp_path):
        from storyboard_gen.subtitles import parse_subtitle_file

        txt = tmp_path / "subs.txt"
        txt.write_text("Hello")

        with pytest.raises(ValueError, match="Unsupported subtitle format"):
            parse_subtitle_file(txt)


class TestParseVtt:
    """Tests for WebVTT parsing."""

    def test_basic_vtt(self):
        from storyboard_gen.subtitles import parse_vtt

        content = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello\n"

        result = parse_vtt(content)

        assert len(result) == 1
        assert result[0].start_ms == 1000
        assert result[0].end_ms == 2000
        assert result[0].text == "Hello"

    def test_vtt_without_hours(self):
        from storyboard_gen.subtitles import parse_vtt

        content = "WEBVTT\n\n01:30.500 --> 02:00.000\nShort format\n"

        result = parse_vtt(content)

        assert len(result) == 1
        assert result[0].start_ms == 90500
        assert result[0].end_ms == 120000

    def test_vtt_multiline_text(self):
        from storyboard_gen.subtitles import parse_vtt

        content = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nLine one\nLine two\n"

        result = parse_vtt(content)

        assert len(result) == 1
        assert result[0].text == "Line one\nLine two"

    def test_vtt_multiple_cues(self):
        from storyboard_gen.subtitles import parse_vtt

        content = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:02.000\nFirst\n\n"
            "00:00:03.000 --> 00:00:04.000\nSecond\n"
        )

        result = parse_vtt(content)

        assert len(result) == 2
        assert result[0].text == "First"
        assert result[1].text == "Second"
        assert result[0].index == 1
        assert result[1].index == 2

    def test_vtt_with_cue_identifiers(self):
        """VTT cue identifiers (optional labels) should be skipped."""
        from storyboard_gen.subtitles import parse_vtt

        content = "WEBVTT\n\nintro\n00:00:01.000 --> 00:00:02.000\nHello\n"

        result = parse_vtt(content)

        assert len(result) == 1
        assert result[0].text == "Hello"

    def test_vtt_with_positioning(self):
        """VTT positioning metadata after --> should be ignored."""
        from storyboard_gen.subtitles import parse_vtt

        content = (
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000 position:50% line:80%\nHello\n"
        )

        result = parse_vtt(content)

        assert len(result) == 1
        assert result[0].text == "Hello"

    def test_vtt_windows_line_endings(self):
        from storyboard_gen.subtitles import parse_vtt

        content = "WEBVTT\r\n\r\n00:00:01.000 --> 00:00:02.000\r\nHello\r\n"

        result = parse_vtt(content)

        assert len(result) == 1
        assert result[0].text == "Hello"

    def test_vtt_missing_header_raises(self):
        from storyboard_gen.subtitles import parse_vtt

        content = "00:00:01.000 --> 00:00:02.000\nHello\n"

        with pytest.raises(ValueError, match="WEBVTT"):
            parse_vtt(content)


class TestParseAss:
    """Tests for ASS/SSA parsing."""

    def test_basic_ass(self):
        from storyboard_gen.subtitles import parse_ass

        content = (
            "[Script Info]\nScriptType: v4.00+\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello world\n"
        )

        result = parse_ass(content)

        assert len(result) == 1
        assert result[0].start_ms == 1000
        assert result[0].end_ms == 2000
        assert result[0].text == "Hello world"

    def test_ass_centisecond_precision(self):
        from storyboard_gen.subtitles import parse_ass

        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.90,0:00:04.33,Default,,0,0,0,,Test\n"
        )

        result = parse_ass(content)

        assert result[0].start_ms == 1900
        assert result[0].end_ms == 4330

    def test_ass_multiline_text_with_newline_marker(self):
        """ASS uses \\N for line breaks in dialogue text."""
        from storyboard_gen.subtitles import parse_ass

        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Line one\\NLine two\n"
        )

        result = parse_ass(content)

        assert result[0].text == "Line one\nLine two"

    def test_ass_multiple_dialogues(self):
        from storyboard_gen.subtitles import parse_ass

        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,First\n"
            "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,Second\n"
        )

        result = parse_ass(content)

        assert len(result) == 2
        assert result[0].text == "First"
        assert result[1].text == "Second"

    def test_ass_ignores_comment_lines(self):
        from storyboard_gen.subtitles import parse_ass

        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Comment: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,This is a comment\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n"
        )

        result = parse_ass(content)

        assert len(result) == 1
        assert result[0].text == "Hello"

    def test_ass_text_with_commas(self):
        """Text field may contain commas — everything after the 9th comma is text."""
        from storyboard_gen.subtitles import parse_ass

        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello, world, foo\n"
        )

        result = parse_ass(content)

        assert result[0].text == "Hello, world, foo"


class TestToAss:
    """Tests for converting Subtitle objects to Kdenlive-compatible ASS format."""

    def test_basic_conversion(self):
        from storyboard_gen.subtitles import to_ass

        subs = [Subtitle(index=1, start_ms=1000, end_ms=2000, text="Hello")]

        result = to_ass(subs, width=1920, height=1080)

        assert "[Script Info]" in result
        assert "PlayResX: 1920" in result
        assert "PlayResY: 1080" in result
        assert "[V4+ Styles]" in result
        assert "[Events]" in result
        assert "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello" in result

    def test_multiline_text_uses_ass_newlines(self):
        from storyboard_gen.subtitles import to_ass

        subs = [Subtitle(index=1, start_ms=0, end_ms=1000, text="Line one\nLine two")]

        result = to_ass(subs, width=1920, height=1080)

        assert "Line one\\NLine two" in result

    def test_centisecond_precision(self):
        from storyboard_gen.subtitles import to_ass

        subs = [Subtitle(index=1, start_ms=1900, end_ms=4330, text="Test")]

        result = to_ass(subs, width=1920, height=1080)

        assert "0:00:01.90" in result
        assert "0:00:04.33" in result

    def test_hour_timecodes(self):
        from storyboard_gen.subtitles import to_ass

        subs = [Subtitle(index=1, start_ms=3661500, end_ms=3662000, text="Test")]

        result = to_ass(subs, width=1920, height=1080)

        # 1h 1m 1s 500ms = 1:01:01.50
        assert "1:01:01.50" in result

    def test_multiple_subtitles(self):
        from storyboard_gen.subtitles import to_ass

        subs = [
            Subtitle(index=1, start_ms=0, end_ms=1000, text="First"),
            Subtitle(index=2, start_ms=2000, end_ms=3000, text="Second"),
        ]

        result = to_ass(subs, width=1920, height=1080)

        lines = result.split("\n")
        dialogue_lines = [line for line in lines if line.startswith("Dialogue:")]
        assert len(dialogue_lines) == 2

    def test_empty_subtitles(self):
        from storyboard_gen.subtitles import to_ass

        result = to_ass([], width=1920, height=1080)

        assert "[Script Info]" in result
        assert "[Events]" in result

    def test_kdenlive_extra_data_section(self):
        """ASS output should include Kdenlive Extradata section for compatibility."""
        from storyboard_gen.subtitles import to_ass

        subs = [Subtitle(index=1, start_ms=0, end_ms=1000, text="Hello")]

        result = to_ass(subs, width=1920, height=1080)

        assert "[Kdenlive Extradata]" in result
