# ABOUTME: Multi-format subtitle parser and ASS writer for storyboard-gen.
# ABOUTME: Supports SRT, VTT, ASS/SSA input; converts to Kdenlive-native ASS output.

import re
from pathlib import Path

from storyboard_gen.srt import Subtitle, parse_srt

_VTT_TC_RE = re.compile(r"^(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})")

_ASS_TC_RE = re.compile(r"^(\d+):(\d{2}):(\d{2})\.(\d{2})$")

# Supported subtitle file extensions.
_FORMATS = {".srt", ".vtt", ".ass", ".ssa"}


def parse_subtitle_file(path: Path) -> list[Subtitle]:
    """Parse a subtitle file, auto-detecting format from extension.

    Args:
        path: Path to subtitle file (.srt, .vtt, .ass, .ssa).

    Returns:
        List of Subtitle objects in order.

    Raises:
        ValueError: If the file extension is not supported.
    """
    ext = path.suffix.lower()
    content = path.read_text(encoding="utf-8")

    if ext == ".srt":
        return parse_srt(content)
    if ext == ".vtt":
        return parse_vtt(content)
    if ext in (".ass", ".ssa"):
        return parse_ass(content)

    raise ValueError(
        f"Unsupported subtitle format '{ext}'. Supported: {', '.join(sorted(_FORMATS))}"
    )


# ---------------------------------------------------------------------------
# WebVTT parser
# ---------------------------------------------------------------------------


def _parse_vtt_timecode(tc: str) -> int:
    """Convert a VTT timecode to milliseconds.

    Accepts both HH:MM:SS.mmm and MM:SS.mmm formats.
    """
    match = _VTT_TC_RE.match(tc.strip())
    if not match:
        raise ValueError(f"Invalid VTT timecode: {tc!r}")
    hours_str, minutes_str, seconds_str, millis_str = match.groups()
    hours = int(hours_str) if hours_str else 0
    return (
        hours * 3600000
        + int(minutes_str) * 60000
        + int(seconds_str) * 1000
        + int(millis_str)
    )


def parse_vtt(content: str) -> list[Subtitle]:
    """Parse WebVTT subtitle content into a list of Subtitle objects.

    Args:
        content: Raw VTT file content (must start with WEBVTT header).

    Returns:
        List of Subtitle objects in order.

    Raises:
        ValueError: If the WEBVTT header is missing or timecodes are malformed.
    """
    content = content.replace("\r\n", "\n")

    if not content.strip().startswith("WEBVTT"):
        raise ValueError("Not a valid WebVTT file — missing WEBVTT header")

    # Remove the header block (everything before first blank line)
    parts = content.split("\n\n", 1)
    body = parts[1] if len(parts) > 1 else ""

    blocks = re.split(r"\n\n+", body.strip())

    subtitles: list[Subtitle] = []
    index = 0
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split("\n")

        # Find the timecode line (contains " --> ")
        tc_line_idx = None
        for i, line in enumerate(lines):
            if " --> " in line:
                tc_line_idx = i
                break

        if tc_line_idx is None:
            continue

        # Parse timecodes (strip any positioning metadata after the end timecode)
        tc_line = lines[tc_line_idx]
        arrow_parts = tc_line.split(" --> ")
        start_tc = arrow_parts[0].strip()
        # End timecode may have positioning info after a space
        end_part = arrow_parts[1].strip()
        end_tc = end_part.split(" ")[0]

        start_ms = _parse_vtt_timecode(start_tc)
        end_ms = _parse_vtt_timecode(end_tc)

        # Text is everything after the timecode line
        text = "\n".join(lines[tc_line_idx + 1 :])

        index += 1
        subtitles.append(
            Subtitle(index=index, start_ms=start_ms, end_ms=end_ms, text=text)
        )

    return subtitles


# ---------------------------------------------------------------------------
# ASS/SSA parser
# ---------------------------------------------------------------------------


def _parse_ass_timecode(tc: str) -> int:
    """Convert an ASS timecode (H:MM:SS.cc) to milliseconds."""
    match = _ASS_TC_RE.match(tc.strip())
    if not match:
        raise ValueError(f"Invalid ASS timecode: {tc!r}")
    hours, minutes, seconds, centis = (int(g) for g in match.groups())
    return hours * 3600000 + minutes * 60000 + seconds * 1000 + centis * 10


def parse_ass(content: str) -> list[Subtitle]:
    """Parse ASS/SSA subtitle content into a list of Subtitle objects.

    Only extracts Dialogue lines from the [Events] section. Comment lines
    and other event types are ignored.

    Args:
        content: Raw ASS/SSA file content.

    Returns:
        List of Subtitle objects in order.
    """
    content = content.replace("\r\n", "\n")

    # Find the [Events] section
    in_events = False
    subtitles: list[Subtitle] = []
    index = 0

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.lower() == "[events]":
            in_events = True
            continue
        if stripped.startswith("[") and in_events:
            break  # Next section
        if not in_events:
            continue
        if not stripped.startswith("Dialogue:"):
            continue

        # Dialogue line: "Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text"
        # Text is everything after the 9th comma (may contain commas)
        after_prefix = stripped[len("Dialogue:") :].strip()
        parts = after_prefix.split(",", 9)
        if len(parts) < 10:
            continue

        start_ms = _parse_ass_timecode(parts[1])
        end_ms = _parse_ass_timecode(parts[2])
        text = parts[9]

        # ASS uses \N for line breaks
        text = text.replace("\\N", "\n")

        index += 1
        subtitles.append(
            Subtitle(index=index, start_ms=start_ms, end_ms=end_ms, text=text)
        )

    return subtitles


# ---------------------------------------------------------------------------
# ASS writer (Kdenlive-compatible output)
# ---------------------------------------------------------------------------


def _ms_to_ass_timecode(ms: int) -> str:
    """Convert milliseconds to ASS timecode format (H:MM:SS.cc)."""
    total_seconds = ms // 1000
    centiseconds = (ms % 1000) // 10
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def to_ass(subtitles: list[Subtitle], width: int, height: int) -> str:
    """Convert Subtitle objects to Kdenlive-compatible ASS format.

    Generates an ASS file matching Kdenlive's expected structure:
    Script Info, Kdenlive Extradata, V4+ Styles, and Events sections.

    Args:
        subtitles: List of Subtitle objects.
        width: Video width for PlayResX.
        height: Video height for PlayResY.

    Returns:
        Complete ASS file content as a string.
    """
    # Scale font size relative to vertical resolution
    font_size = f"{height * 0.055:.2f}"

    lines = [
        "[Script Info]",
        "; Script generated by storyboard-gen",
        f"LayoutResX: {width}",
        f"LayoutResY: {height}",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "ScaledBorderAndShadow: yes",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "YCbCr Matrix: None",
        "",
        "[Kdenlive Extradata]",
        "MaxLayer: 0",
        "DefaultStyles: Default",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Arial Narrow,{font_size},&H00D6D6D6,&H00922FFF,"
        "&H005E5E5E,&H00931B53,0,0,0,0,100.00,100.00,0.00,0.00,1,1.00,"
        f"0.00,2,100,100,{height // 10},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for sub in subtitles:
        start = _ms_to_ass_timecode(sub.start_ms)
        end = _ms_to_ass_timecode(sub.end_ms)
        # Convert newlines to ASS line breaks
        text = sub.text.replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    lines.append("")  # trailing newline
    return "\n".join(lines)
