# ABOUTME: SRT subtitle file parser for storyboard-gen.
# ABOUTME: Parses .srt files into Subtitle dataclasses for Kdenlive export.

import re
from dataclasses import dataclass


_TIMECODE_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$")


@dataclass(frozen=True)
class Subtitle:
    """A single subtitle entry from an SRT file."""

    index: int
    start_ms: int
    end_ms: int
    text: str


def _parse_timecode(tc: str) -> int:
    """Convert an SRT timecode (HH:MM:SS,mmm) to milliseconds.

    Args:
        tc: Timecode string in SRT format.

    Returns:
        Total milliseconds.

    Raises:
        ValueError: If the timecode format is invalid.
    """
    match = _TIMECODE_RE.match(tc.strip())
    if not match:
        raise ValueError(f"Invalid SRT timecode: {tc!r}")
    hours, minutes, seconds, millis = (int(g) for g in match.groups())
    return hours * 3600000 + minutes * 60000 + seconds * 1000 + millis


def parse_srt(content: str) -> list[Subtitle]:
    """Parse SRT subtitle content into a list of Subtitle objects.

    Handles Windows (\\r\\n) and Unix (\\n) line endings, trailing
    newlines, and multiline subtitle text.

    Args:
        content: Raw SRT file content.

    Returns:
        List of Subtitle objects in order.

    Raises:
        ValueError: If a timecode line is malformed.
    """
    # Normalise line endings
    content = content.replace("\r\n", "\n")

    # Split on blank lines into blocks
    blocks = re.split(r"\n\n+", content.strip())

    subtitles: list[Subtitle] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split("\n")
        if len(lines) < 3:
            # Minimum: index, timecodes, one line of text
            # But timecode line might be on line[1] — parse it to get
            # a clear error if malformed
            if len(lines) >= 2:
                _parse_timecodes(lines[1])
            continue

        index = int(lines[0])
        start_ms, end_ms = _parse_timecodes(lines[1])
        text = "\n".join(lines[2:])

        subtitles.append(
            Subtitle(index=index, start_ms=start_ms, end_ms=end_ms, text=text)
        )

    return subtitles


def _parse_timecodes(line: str) -> tuple[int, int]:
    """Parse a timecode line 'HH:MM:SS,mmm --> HH:MM:SS,mmm'.

    Returns (start_ms, end_ms).
    """
    parts = line.strip().split(" --> ")
    if len(parts) != 2:
        raise ValueError(f"Invalid SRT timecode line: {line!r}")
    return _parse_timecode(parts[0]), _parse_timecode(parts[1])
