# ABOUTME: Final Cut Pro FCPXML project file generator for storyboard-gen.
# ABOUTME: Exports an FCPXML 1.14 project for timeline editing with Ken Burns transform effects.

import logging
import uuid
import xml.dom.minidom
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

from storyboard_gen.kdenlive import _probe_audio
from storyboard_gen.ken_burns import ASPECT_DIMENSIONS
from storyboard_gen.models import Project, Scene, format_scene_number

logger = logging.getLogger(__name__)

# FCPXML version targeting Final Cut Pro 12 (Creator Studio)
_FCPXML_VERSION = "1.14"

# Scale factor for pan/zoom effects (matches ken_burns.py's 1.2x)
_KB_SCALE = 1.2

# FCP uses a large start offset for stills placed on the timeline.
# This matches the value observed in FCP 12 exports.
_STILL_START = "3600s"


def generate_fcpxml(
    project: Project,
    output_dir: Path,
    output_filename: str | None = None,
    audio_path: Path | None = None,
    subtitles_path: Path | None = None,
    fps: int = 30,
) -> Path:
    """Generate a Final Cut Pro project file (.fcpxml) from a storyboard project.

    Args:
        project: The project definition.
        output_dir: Base output directory (contains stills/, clips/).
        output_filename: Custom output filename. Defaults to "{title}.fcpxml".
        audio_path: Optional path to an audio file to include.
        subtitles_path: Optional path to a subtitle file to include.
        fps: Frames per second.

    Returns:
        Path to the generated .fcpxml file.

    Raises:
        FileNotFoundError: If expected scene files are missing.
    """
    for scene in project.scenes:
        clip_path = _resolve_clip_path(scene, output_dir)
        if not clip_path.exists():
            raise FileNotFoundError(
                f"Missing clip for scene {scene.number} ({scene.title}): {clip_path}"
            )

    if output_filename is None:
        output_filename = f"{project.filename_stem}.fcpxml"

    final_dir = output_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    output_path = final_dir / output_filename

    fcpxml = _build_fcpxml(project, output_dir, fps, audio_path, subtitles_path)

    rough_string = ET.tostring(fcpxml, encoding="unicode")
    dom = xml.dom.minidom.parseString(rough_string)
    pretty_xml = dom.toprettyxml(indent="  ", encoding=None)

    # Insert DOCTYPE and fix encoding in XML declaration
    lines = pretty_xml.split("\n", 1)
    xml_decl = '<?xml version="1.0" encoding="UTF-8"?>'
    output_text = xml_decl + "\n<!DOCTYPE fcpxml>\n" + lines[1]

    output_path.write_text(output_text, encoding="utf-8")
    logger.info("FCPXML project: %s", output_path)
    return output_path


def _resolve_clip_path(scene: Scene, output_dir: Path) -> Path:
    """Resolve the clip path for a scene."""
    if scene.scene_type == "still":
        return output_dir / "stills" / f"scene_{format_scene_number(scene.number)}.png"
    return output_dir / "clips" / f"scene_{format_scene_number(scene.number)}.mp4"


def _rational_time(seconds: float, fps: int) -> str:
    """Convert seconds to FCPXML rational time string.

    For integer fps (24, 25, 30, 60), uses denominator = fps * 100.
    All times land on edit frame boundaries.
    """
    if seconds == 0:
        return "0s"
    denominator = fps * 100
    frame_duration = 100  # for integer fps
    frame_count = round(seconds * fps)
    numerator = frame_count * frame_duration
    return f"{numerator}/{denominator}s"


def _frame_duration(fps: int) -> str:
    """Return the frame duration string for a given fps."""
    return f"100/{fps * 100}s"


def _file_uri(path: Path) -> str:
    """Convert a filesystem path to a file:// URI."""
    abs_path = str(path.resolve())
    return "file://" + quote(abs_path, safe="/:")


def _make_uid() -> str:
    """Generate a UUID string for FCPXML uid attributes."""
    return str(uuid.uuid4()).upper()


# AssetInfo: (asset_id, scene, duration_rational, is_still)
AssetInfo = tuple[str, Scene, str, bool]


def _build_fcpxml(
    project: Project,
    output_dir: Path,
    fps: int,
    audio_path: Path | None,
    subtitles_path: Path | None,
) -> ET.Element:
    """Build the FCPXML document tree."""
    root = ET.Element("fcpxml", version=_FCPXML_VERSION)

    aspect_ratio = project.aspect_ratio
    width, height = ASPECT_DIMENSIONS.get(aspect_ratio, (1920, 1080))

    resources = ET.SubElement(root, "resources")

    # Format resource
    format_id = "r1"
    ET.SubElement(
        resources,
        "format",
        id=format_id,
        frameDuration=_frame_duration(fps),
        width=str(width),
        height=str(height),
        colorSpace="1-1-1 (Rec. 709)",
    )

    # Scene assets
    asset_id_counter = 2  # r1 is the format
    assets: list[AssetInfo] = []
    for scene in project.scenes:
        clip_path = _resolve_clip_path(scene, output_dir)
        is_still = scene.scene_type == "still"
        asset_id = f"r{asset_id_counter}"
        duration_rational = _rational_time(scene.duration, fps)

        asset_attrs = {
            "id": asset_id,
            "name": f"scene_{format_scene_number(scene.number)}",
            "uid": _make_uid().replace("-", ""),
            "start": "0s",
            "duration": "0s" if is_still else duration_rational,
            "hasVideo": "1",
            "format": format_id,
            "videoSources": "1",
        }
        if not is_still:
            asset_attrs["hasAudio"] = "1"
            asset_attrs["audioSources"] = "1"
            asset_attrs["audioChannels"] = "2"
            asset_attrs["audioRate"] = "48000"
        asset_elem = ET.SubElement(resources, "asset", **asset_attrs)
        ET.SubElement(
            asset_elem, "media-rep", kind="original-media", src=_file_uri(clip_path)
        )
        assets.append((asset_id, scene, duration_rational, is_still))
        asset_id_counter += 1

    # Audio asset — probe file for actual sample rate, channels, and duration
    audio_asset_id = None
    audio_format_id = None
    if audio_path is not None:
        # Audio-only format (FCP uses FFVideoFormatRateUndefined for audio)
        audio_format_id = f"r{asset_id_counter}"
        ET.SubElement(
            resources, "format", id=audio_format_id, name="FFVideoFormatRateUndefined"
        )
        asset_id_counter += 1

        audio_asset_id = f"r{asset_id_counter}"
        audio_info = _probe_audio(audio_path)
        sample_rate = int(audio_info["sample_rate"]) if audio_info else 48000
        channels = str(audio_info["channels"]) if audio_info else "2"
        audio_duration = _probe_audio_duration(audio_path, sample_rate)
        audio_asset = ET.SubElement(
            resources,
            "asset",
            id=audio_asset_id,
            name=audio_path.stem,
            uid=_make_uid().replace("-", ""),
            start="0s",
            duration=audio_duration,
            hasAudio="1",
            audioSources="1",
            audioChannels=channels,
            audioRate=str(sample_rate),
        )
        ET.SubElement(
            audio_asset, "media-rep", kind="original-media", src=_file_uri(audio_path)
        )
        asset_id_counter += 1

    # Title effect (for subtitles)
    title_effect_id = None
    subtitle_cues = []
    if subtitles_path is not None:
        title_effect_id = f"r{asset_id_counter}"
        ET.SubElement(
            resources,
            "effect",
            id=title_effect_id,
            name="Basic Title",
            uid=".../Titles.localized/Bumper:Opener.localized/"
            "Basic Title.localized/Basic Title.moti",
        )
        asset_id_counter += 1
        subtitle_cues = _parse_subtitles(subtitles_path)

    # Total duration
    total_duration = sum(s.duration for s in project.scenes)
    total_rational = _rational_time(total_duration, fps)

    # Library → Event → Project → Sequence → Spine
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", name=project.title, uid=_make_uid())

    # Register audio as event-level clip so FCP imports the media
    if audio_asset_id is not None:
        ET.SubElement(
            event,
            "asset-clip",
            ref=audio_asset_id,
            name=audio_path.stem,
            duration=audio_duration,
            format=audio_format_id,
            audioRole="dialogue",
        )

    proj = ET.SubElement(event, "project", name=project.title, uid=_make_uid())
    sequence = ET.SubElement(
        proj,
        "sequence",
        format=format_id,
        duration=total_rational,
        tcStart="0s",
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate="48k",
    )
    spine = ET.SubElement(sequence, "spine")

    # Place clips on the spine
    offset_seconds = 0.0
    subtitle_counter = 0
    for asset_id, scene, duration_rational, is_still in assets:
        offset_rational = _rational_time(offset_seconds, fps)

        if is_still:
            # FCP uses <video> for still images on the spine
            clip = ET.SubElement(
                spine,
                "video",
                ref=asset_id,
                offset=offset_rational,
                name=scene.title,
                start=_STILL_START,
                duration=duration_rational,
            )
        else:
            # FCP uses <asset-clip> for video clips
            clip = ET.SubElement(
                spine,
                "asset-clip",
                ref=asset_id,
                offset=offset_rational,
                name=scene.title,
                duration=duration_rational,
                format=format_id,
                tcFormat="NDF",
                audioRole="dialogue",
            )

        # Ken Burns crop (stills only)
        ken_burns = scene.ken_burns if is_still else None
        if ken_burns and ken_burns != "static":
            _add_ken_burns_crop(clip, ken_burns, width, height)

        # Audio lane (attached to first clip, spanning full timeline)
        if audio_asset_id is not None and offset_seconds == 0.0:
            # Duration in simple seconds matching FCP's export format
            total_secs = (
                f"{int(total_duration)}s"
                if total_duration == int(total_duration)
                else f"{total_duration}s"
            )
            # Offset matches parent video's start for correct alignment
            audio_offset = _STILL_START if is_still else "0s"
            ET.SubElement(
                clip,
                "asset-clip",
                ref=audio_asset_id,
                lane="-1",
                offset=audio_offset,
                name=audio_path.stem,
                duration=total_secs,
                format=audio_format_id,
                audioRole="dialogue",
            )

        # Subtitle titles (attached to clips they overlap)
        if title_effect_id and subtitle_cues:
            for cue_start, cue_end, cue_text in subtitle_cues:
                clip_start = offset_seconds
                clip_end = offset_seconds + scene.duration
                if cue_start < clip_end and cue_end > clip_start:
                    local_start = max(0.0, cue_start - clip_start)
                    local_end = min(scene.duration, cue_end - clip_start)
                    local_duration = local_end - local_start
                    # Skip subtitles shorter than one frame (FCP rejects 0-duration titles)
                    if local_duration >= 1.0 / fps:
                        title = ET.SubElement(
                            clip,
                            "title",
                            ref=title_effect_id,
                            lane="1",
                            offset=_rational_time(local_start, fps),
                            duration=_rational_time(local_duration, fps),
                            name="Subtitle",
                        )
                        # Params required by Basic Title for rendering
                        ET.SubElement(
                            title,
                            "param",
                            name="Flatten",
                            key="9999/999166631/999166633/2/351",
                            value="1",
                        )
                        ET.SubElement(
                            title,
                            "param",
                            name="Alignment",
                            key="9999/999166631/999166633/2/354/999169573/401",
                            value="1 (Center)",
                        )
                        subtitle_counter += 1
                        ts_id = f"ts{subtitle_counter}"
                        text_elem = ET.SubElement(title, "text")
                        ts = ET.SubElement(text_elem, "text-style", ref=ts_id)
                        ts.text = cue_text
                        ts_def = ET.SubElement(title, "text-style-def", id=ts_id)
                        ET.SubElement(
                            ts_def,
                            "text-style",
                            font="Helvetica",
                            fontSize="48",
                            fontColor="1 1 1 1",
                            alignment="center",
                        )

        offset_seconds += scene.duration

    return root


def _add_ken_burns_crop(
    clip: ET.Element,
    ken_burns: str,
    width: int,
    height: int,
) -> None:
    """Add FCP-native Ken Burns effect using adjust-crop pan mode.

    FCP represents Ken Burns as ``<adjust-crop mode="pan">`` with two
    ``<pan-rect>`` children defining start and end crop rectangles.
    All four values (left, top, right, bottom) are in units of
    **percentage of original frame height** — even the horizontal ones.
    Full frame = all zeros; zoomed = positive insets.
    """
    # For a 1.2x scale, crop fraction per side = (1 - 1/scale) / 2
    crop_frac = (1 - 1 / _KB_SCALE) / 2
    # Top/bottom: straightforward % of height
    v_inset = round(crop_frac * 100, 4)
    # Left/right: convert from width-fraction to height-percentage units
    h_inset = round(crop_frac * width / height * 100, 4)

    # Full frame (no crop)
    full = {"left": "0", "top": "0", "right": "0", "bottom": "0"}
    # Uniformly cropped (zoomed in)
    zoomed = {
        "left": str(h_inset),
        "top": str(v_inset),
        "right": str(h_inset),
        "bottom": str(v_inset),
    }

    if ken_burns == "zoom_in":
        # Start full, end zoomed
        start_rect = full
        end_rect = zoomed
    elif ken_burns == "zoom_out":
        # Start zoomed, end full
        start_rect = zoomed
        end_rect = full
    elif ken_burns == "pan_ltr":
        # Pan left to right: start cropped on left, end cropped on right
        h_total = h_inset * 2
        start_rect = {
            "left": str(round(h_total, 4)),
            "top": str(v_inset),
            "right": "0",
            "bottom": str(v_inset),
        }
        end_rect = {
            "left": "0",
            "top": str(v_inset),
            "right": str(round(h_total, 4)),
            "bottom": str(v_inset),
        }
    elif ken_burns == "pan_rtl":
        # Pan right to left: start cropped on right, end cropped on left
        h_total = h_inset * 2
        start_rect = {
            "left": "0",
            "top": str(v_inset),
            "right": str(round(h_total, 4)),
            "bottom": str(v_inset),
        }
        end_rect = {
            "left": str(round(h_total, 4)),
            "top": str(v_inset),
            "right": "0",
            "bottom": str(v_inset),
        }
    else:
        logger.warning("Unknown ken_burns value %r, skipping crop", ken_burns)
        return

    crop = ET.SubElement(clip, "adjust-crop", mode="pan")
    ET.SubElement(crop, "pan-rect", **start_rect)
    ET.SubElement(crop, "pan-rect", **end_rect)


def _probe_audio_duration(audio_path: Path, sample_rate: int) -> str:
    """Probe audio file duration and return as FCPXML rational time.

    FCP expects audio asset duration expressed in the file's native
    sample rate, e.g. ``1560964/44100s`` for a 44.1kHz file.
    Falls back to ``0s`` if ffprobe is unavailable.
    """
    import json
    import subprocess

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_entries",
                "format=duration",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "0s"

    if result.returncode != 0:
        return "0s"

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "0s"

    duration_str = data.get("format", {}).get("duration")
    if not duration_str:
        return "0s"

    duration_secs = float(duration_str)
    # Convert to samples at native rate for exact representation
    samples = round(duration_secs * sample_rate)
    return f"{samples}/{sample_rate}s"


def _parse_subtitles(subtitles_path: Path) -> list[tuple[float, float, str]]:
    """Parse a subtitle file and return (start_seconds, end_seconds, text) tuples."""
    from storyboard_gen.subtitles import parse_subtitle_file

    subs = parse_subtitle_file(subtitles_path)
    return [(s.start_ms / 1000.0, s.end_ms / 1000.0, s.text) for s in subs]
