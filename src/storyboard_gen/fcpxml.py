# ABOUTME: Final Cut Pro FCPXML project file generator for storyboard-gen.
# ABOUTME: Exports an FCPXML 1.14 project for timeline editing with Ken Burns transform effects.

import logging
import uuid
import xml.dom.minidom
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

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

    # Audio asset
    audio_asset_id = None
    if audio_path is not None:
        audio_asset_id = f"r{asset_id_counter}"
        audio_asset = ET.SubElement(
            resources,
            "asset",
            id=audio_asset_id,
            name=audio_path.stem,
            uid=_make_uid().replace("-", ""),
            start="0s",
            duration="0s",
            hasAudio="1",
            audioSources="1",
            audioChannels="2",
            audioRate="48000",
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

        # Audio lane (attached to first clip only, spanning full timeline)
        if audio_asset_id is not None and offset_seconds == 0.0:
            ET.SubElement(
                clip,
                "audio",
                ref=audio_asset_id,
                lane="-1",
                offset="0s",
                duration=total_rational,
                start="0s",
                role="music",
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
                    if local_duration > 0:
                        title = ET.SubElement(
                            clip,
                            "title",
                            ref=title_effect_id,
                            lane="1",
                            offset=_rational_time(local_start, fps),
                            duration=_rational_time(local_duration, fps),
                            name="Subtitle",
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
    Values are percentage insets from each edge: left, top, right, bottom.
    Full frame = all zeros; zoomed = positive insets.
    """
    # For a 1.2x scale, the cropped region is 1/1.2 = 83.3% of the frame.
    # Inset on each side = (1 - 1/scale) / 2 * 100
    inset_pct = (1 - 1 / _KB_SCALE) / 2 * 100
    # Horizontal and vertical insets may differ for panning
    h_inset = round(inset_pct, 4)
    v_inset = round(inset_pct, 4)

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


def _parse_subtitles(subtitles_path: Path) -> list[tuple[float, float, str]]:
    """Parse a subtitle file and return (start_seconds, end_seconds, text) tuples."""
    from storyboard_gen.subtitles import parse_subtitle_file

    subs = parse_subtitle_file(subtitles_path)
    return [(s.start_ms / 1000.0, s.end_ms / 1000.0, s.text) for s in subs]
