# ABOUTME: Tests for storyboard_gen.srt.
# ABOUTME: Validates SRT subtitle parsing including timecodes, multiline text, and edge cases.

import pytest

from storyboard_gen.srt import Subtitle, parse_srt, _parse_timecode


class TestParseTimecode:
    def test_zero_timecode(self):
        # Arrange & Act & Assert
        assert _parse_timecode("00:00:00,000") == 0

    def test_hours(self):
        # Arrange & Act & Assert
        assert _parse_timecode("01:00:00,000") == 3600000

    def test_minutes(self):
        # Arrange & Act & Assert
        assert _parse_timecode("00:05:00,000") == 300000

    def test_seconds(self):
        # Arrange & Act & Assert
        assert _parse_timecode("00:00:30,000") == 30000

    def test_milliseconds(self):
        # Arrange & Act & Assert
        assert _parse_timecode("00:00:00,500") == 500

    def test_combined(self):
        # Arrange & Act & Assert
        assert _parse_timecode("01:02:03,456") == 3723456

    def test_leading_zeros(self):
        # Arrange & Act & Assert
        assert _parse_timecode("00:00:01,001") == 1001

    def test_malformed_timecode_raises(self):
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Invalid SRT timecode"):
            _parse_timecode("1:2:3")

    def test_missing_comma_raises(self):
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="Invalid SRT timecode"):
            _parse_timecode("00:00:00.000")


class TestParseSrt:
    def test_single_entry(self):
        # Arrange
        content = "1\n00:00:01,000 --> 00:00:04,000\nHello, world!\n"

        # Act
        result = parse_srt(content)

        # Assert
        assert len(result) == 1
        assert result[0] == Subtitle(
            index=1, start_ms=1000, end_ms=4000, text="Hello, world!"
        )

    def test_multiple_entries(self):
        # Arrange
        content = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000\n"
            "First subtitle.\n"
            "\n"
            "2\n"
            "00:00:05,000 --> 00:00:08,500\n"
            "Second subtitle.\n"
        )

        # Act
        result = parse_srt(content)

        # Assert
        assert len(result) == 2
        assert result[0].index == 1
        assert result[0].text == "First subtitle."
        assert result[1].index == 2
        assert result[1].start_ms == 5000
        assert result[1].end_ms == 8500
        assert result[1].text == "Second subtitle."

    def test_multiline_text(self):
        # Arrange
        content = "1\n00:00:01,000 --> 00:00:04,000\nLine one\nLine two\n"

        # Act
        result = parse_srt(content)

        # Assert
        assert result[0].text == "Line one\nLine two"

    def test_empty_string_returns_empty_list(self):
        # Arrange & Act
        result = parse_srt("")

        # Assert
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        # Arrange & Act
        result = parse_srt("   \n\n  \n")

        # Assert
        assert result == []

    def test_malformed_timecode_raises(self):
        # Arrange
        content = "1\nbad timecode\nSome text\n"

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid SRT timecode"):
            parse_srt(content)

    def test_trailing_newlines(self):
        # Arrange
        content = "1\n00:00:01,000 --> 00:00:04,000\nHello!\n\n\n\n"

        # Act
        result = parse_srt(content)

        # Assert
        assert len(result) == 1
        assert result[0].text == "Hello!"

    def test_windows_line_endings(self):
        # Arrange
        content = (
            "1\r\n"
            "00:00:01,000 --> 00:00:04,000\r\n"
            "Windows subtitle.\r\n"
            "\r\n"
            "2\r\n"
            "00:00:05,000 --> 00:00:08,000\r\n"
            "Second line.\r\n"
        )

        # Act
        result = parse_srt(content)

        # Assert
        assert len(result) == 2
        assert result[0].text == "Windows subtitle."
        assert result[1].text == "Second line."

    def test_subtitle_is_frozen(self):
        # Arrange
        sub = Subtitle(index=1, start_ms=0, end_ms=1000, text="Hello")

        # Act & Assert — frozen dataclass should raise on mutation
        with pytest.raises(AttributeError):
            sub.text = "Changed"
