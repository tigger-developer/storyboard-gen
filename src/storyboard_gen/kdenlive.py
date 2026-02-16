# ABOUTME: Kdenlive project file generator for storyboard-gen.
# ABOUTME: Exports an MLT XML project for timeline editing with Ken Burns transform effects.

import json
import logging
import subprocess
import uuid
import xml.dom.minidom
import xml.etree.ElementTree as ET
from pathlib import Path

from storyboard_gen.ken_burns import ASPECT_DIMENSIONS
from storyboard_gen.models import Project, Scene, format_scene_number

logger = logging.getLogger(__name__)


def generate_kdenlive(
    project: Project,
    output_dir: Path,
    output_filename: str | None = None,
    audio_path: Path | None = None,
    fps: int = 30,
) -> Path:
    """Generate a Kdenlive project file (.kdenlive) from a storyboard project.

    Args:
        project: The project definition.
        output_dir: Base output directory (contains stills/, clips/).
        output_filename: Custom output filename. Defaults to "{title}.kdenlive".
        audio_path: Optional path to an audio file to include.
        fps: Frames per second.

    Returns:
        Path to the generated .kdenlive file.

    Raises:
        FileNotFoundError: If expected scene files are missing.
    """
    # Validate all clip paths exist before building
    for scene in project.scenes:
        clip_path = _resolve_clip_path(scene, output_dir)
        if not clip_path.exists():
            raise FileNotFoundError(
                f"Missing clip for scene {scene.number} ({scene.title}): {clip_path}"
            )

    mlt = _build_mlt(project, output_dir, fps, audio_path)

    if output_filename is None:
        output_filename = f"{project.title}.kdenlive"

    final_dir = output_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    output_path = final_dir / output_filename

    # Pretty-print the XML
    rough_string = ET.tostring(mlt, encoding="unicode")
    dom = xml.dom.minidom.parseString(rough_string)
    pretty_xml = dom.toprettyxml(indent="  ", encoding=None)

    output_path.write_text(pretty_xml)
    logger.info("Kdenlive project: %s", output_path)
    return output_path


def _frames(seconds: float, fps: int) -> int:
    """Convert a duration in seconds to a frame count."""
    return round(seconds * fps)


def _resolve_clip_path(scene: Scene, output_dir: Path) -> Path:
    """Resolve the clip path for a scene.

    Stills use the generated PNG; clips use clips/ directly.
    """
    if scene.scene_type == "still":
        return output_dir / "stills" / f"scene_{format_scene_number(scene.number)}.png"
    return output_dir / "clips" / f"scene_{format_scene_number(scene.number)}.mp4"


# ProducerInfo: (producer_id, length_frames, kdenlive_id, clip_name)
ProducerInfo = tuple[str, int, int, str]


def _build_mlt(
    project: Project,
    output_dir: Path,
    fps: int,
    audio_path: Path | None,
) -> ET.Element:
    """Build the Kdenlive-compatible MLT XML document.

    Returns the root <mlt> Element with proper Kdenlive structure:
    producers, main_bin, video/audio track tractors, sequence tractor,
    and project tractor.
    """
    mlt = ET.Element("mlt")
    mlt.set("producer", "main_bin")
    mlt.set("root", str(output_dir.parent.resolve()))

    # Profile
    aspect_ratio = project.aspect_ratio
    width, height = ASPECT_DIMENSIONS.get(aspect_ratio, (1920, 1080))
    _add_profile(mlt, width, height, fps)

    # Black track producer (Kdenlive timeline background)
    _add_black_track(mlt)

    # Scene producers (kdenlive:id starts at 2; 1 is reserved for the sequence)
    kdenlive_id = 2
    producers: list[ProducerInfo] = []
    for _i, scene in enumerate(project.scenes):
        clip_path = _resolve_clip_path(scene, output_dir)
        length = _frames(scene.duration, fps)
        producer_id = f"producer_{scene.number}"
        is_still = scene.scene_type == "still"
        producer_el = _add_scene_producer(
            mlt,
            producer_id,
            clip_path.resolve(),
            length,
            kdenlive_id,
            scene.title,
            is_still=is_still,
        )
        if is_still:
            _add_ken_burns_filter(producer_el, scene.ken_burns, width, height, length)
        producers.append((producer_id, length, kdenlive_id, scene.title))
        kdenlive_id += 1

    # Audio producer
    audio_info: ProducerInfo | None = None
    if audio_path is not None:
        audio_producer = _add_scene_producer(
            mlt, "audio_producer", audio_path.resolve(), 0, kdenlive_id, "Audio"
        )
        _set_prop(audio_producer, "video_index", "-1")
        _set_prop(audio_producer, "audio_index", "0")
        _set_prop(audio_producer, "kdenlive:clip_type", "1")
        audio_info = ("audio_producer", 0, kdenlive_id, "Audio")
        kdenlive_id += 1

    # Video track
    _build_video_track(mlt, producers)

    # Audio track (if configured)
    has_audio = audio_info is not None
    if has_audio:
        _build_audio_track(mlt, audio_info)

    # Total timeline length in frames
    total_frames = sum(p[1] for p in producers)

    # Sequence tractor (combines all tracks)
    seq_uuid = str(uuid.uuid4())
    _build_sequence_tractor(mlt, total_frames, seq_uuid, has_audio)

    # Main bin (clip library — required by Kdenlive)
    _build_main_bin(mlt, producers, audio_info, seq_uuid, total_frames)

    # Project tractor (wraps active sequence)
    _build_project_tractor(mlt, total_frames)

    return mlt


def _add_profile(mlt: ET.Element, width: int, height: int, fps: int) -> None:
    """Add a <profile> element to the MLT document."""
    ET.SubElement(
        mlt,
        "profile",
        width=str(width),
        height=str(height),
        frame_rate_num=str(fps),
        frame_rate_den="1",
        display_aspect_num=str(width),
        display_aspect_den=str(height),
        progressive="1",
        colorspace="709",
        sample_aspect_num="1",
        sample_aspect_den="1",
    )


def _add_black_track(mlt: ET.Element) -> None:
    """Add the black background producer required by Kdenlive."""
    producer = ET.SubElement(mlt, "producer", id="black_track")
    _set_prop(producer, "resource", "black")
    _set_prop(producer, "mlt_service", "color")
    _set_prop(producer, "kdenlive:playlistid", "black_track")
    _set_prop(producer, "mlt_image_format", "rgba")


def _add_scene_producer(
    mlt: ET.Element,
    producer_id: str,
    path: Path,
    length_frames: int,
    kdenlive_id: int,
    clip_name: str,
    is_still: bool = False,
) -> ET.Element:
    """Add a <producer> element for a scene clip or audio file.

    Returns the producer element for further modification (e.g. adding filters).
    """
    attrs = {"id": producer_id}
    if length_frames > 0:
        attrs["in"] = "0"
        attrs["out"] = str(length_frames - 1)
    producer = ET.SubElement(mlt, "producer", **attrs)
    _set_prop(producer, "resource", str(path))
    if length_frames > 0:
        _set_prop(producer, "length", str(length_frames))
    if is_still:
        _set_prop(producer, "loop", "1")
    _set_prop(producer, "kdenlive:id", str(kdenlive_id))
    _set_prop(producer, "kdenlive:clipname", clip_name)
    return producer


def _build_video_track(mlt: ET.Element, producers: list[ProducerInfo]) -> None:
    """Build sequential video playlists wrapped in a tractor."""
    playlist0 = ET.SubElement(mlt, "playlist", id="playlist0")
    for producer_id, length, kdenlive_id, _name in producers:
        entry = ET.SubElement(
            playlist0,
            "entry",
            producer=producer_id,
            **{"in": "0", "out": str(length - 1)},
        )
        _set_prop(entry, "kdenlive:id", str(kdenlive_id))

    # Empty B playlist (Kdenlive expects A/B pair per track)
    ET.SubElement(mlt, "playlist", id="playlist1")

    # Video track tractor
    tractor = ET.SubElement(mlt, "tractor", id="video_tractor")
    ET.SubElement(tractor, "track", hide="audio", producer="playlist0")
    ET.SubElement(tractor, "track", hide="audio", producer="playlist1")

    # Internal transitions for base compositing
    _add_internal_mix(tractor, "video_track_mix", a_track=0, b_track=1)
    _add_internal_qtblend(tractor, "video_track_blend", a_track=0, b_track=1)


def _build_audio_track(mlt: ET.Element, audio_info: ProducerInfo) -> None:
    """Build an audio track with A/B playlists wrapped in a tractor."""
    producer_id, _length, kdenlive_id, _name = audio_info

    playlist_a = ET.SubElement(mlt, "playlist", id="audio_playlist0")
    _set_prop(playlist_a, "kdenlive:audio_track", "1")
    entry = ET.SubElement(playlist_a, "entry", producer=producer_id)
    _set_prop(entry, "kdenlive:id", str(kdenlive_id))

    # Empty B playlist
    playlist_b = ET.SubElement(mlt, "playlist", id="audio_playlist1")
    _set_prop(playlist_b, "kdenlive:audio_track", "1")

    tractor = ET.SubElement(mlt, "tractor", id="audio_tractor")
    _set_prop(tractor, "kdenlive:audio_track", "1")
    ET.SubElement(tractor, "track", hide="video", producer="audio_playlist0")
    ET.SubElement(tractor, "track", hide="video", producer="audio_playlist1")


def _build_sequence_tractor(
    mlt: ET.Element,
    total_frames: int,
    seq_uuid: str,
    has_audio: bool,
) -> None:
    """Build the sequence tractor that combines all tracks.

    This is the Kdenlive timeline. It includes the black track as
    background and internal mix/qtblend transitions between tracks.
    """
    tractor = ET.SubElement(
        mlt,
        "tractor",
        id="sequence_tractor",
        **{"in": "0", "out": str(max(total_frames - 1, 0))},
    )
    _set_prop(tractor, "kdenlive:uuid", f"{{{seq_uuid}}}")
    _set_prop(tractor, "kdenlive:clipname", "Sequence 1")
    _set_prop(tractor, "kdenlive:id", "1")
    _set_prop(tractor, "kdenlive:producer_type", "17")
    _set_prop(
        tractor, "kdenlive:sequenceproperties.hasAudio", "1" if has_audio else "0"
    )
    _set_prop(tractor, "kdenlive:sequenceproperties.hasVideo", "1")

    # Track 0: black background
    ET.SubElement(tractor, "track", producer="black_track")

    # Audio track (if present) as track 1
    track_index = 1
    if has_audio:
        ET.SubElement(tractor, "track", producer="audio_tractor")
        # mix transition for audio track
        _add_internal_mix(tractor, "seq_mix_audio", a_track=0, b_track=track_index)
        track_index += 1

    # Video track
    ET.SubElement(tractor, "track", producer="video_tractor")
    # qtblend transition for video compositing over black
    _add_internal_qtblend(tractor, "seq_blend_video", a_track=0, b_track=track_index)


def _build_main_bin(
    mlt: ET.Element,
    producers: list[ProducerInfo],
    audio_info: ProducerInfo | None,
    seq_uuid: str,
    total_frames: int,
) -> None:
    """Build the main_bin playlist (Kdenlive's clip library).

    Every producer must be registered here or Kdenlive will reject it.
    """
    main_bin = ET.SubElement(mlt, "playlist", id="main_bin")
    _set_prop(main_bin, "kdenlive:docproperties.version", "1.1")
    _set_prop(main_bin, "kdenlive:docproperties.kdenliveversion", "25.04.0")
    _set_prop(main_bin, "kdenlive:docproperties.uuid", f"{{{seq_uuid}}}")
    _set_prop(main_bin, "kdenlive:docproperties.activetimeline", f"{{{seq_uuid}}}")
    _set_prop(main_bin, "xml_retain", "1")

    # Register all scene producers
    for producer_id, length, _kid, _name in producers:
        attrs = {"producer": producer_id}
        if length > 0:
            attrs["in"] = "0"
            attrs["out"] = str(length - 1)
        ET.SubElement(main_bin, "entry", **attrs)

    # Register audio producer
    if audio_info is not None:
        ET.SubElement(main_bin, "entry", producer=audio_info[0])

    # Register the sequence tractor
    seq_attrs = {"producer": "sequence_tractor"}
    if total_frames > 0:
        seq_attrs["in"] = "0"
        seq_attrs["out"] = str(total_frames - 1)
    ET.SubElement(main_bin, "entry", **seq_attrs)


def _build_project_tractor(mlt: ET.Element, total_frames: int) -> None:
    """Build the project tractor that wraps the active sequence."""
    tractor = ET.SubElement(
        mlt,
        "tractor",
        id="project_tractor",
        **{"in": "0", "out": str(max(total_frames - 1, 0))},
    )
    _set_prop(tractor, "kdenlive:projectTractor", "1")
    ET.SubElement(
        tractor,
        "track",
        producer="sequence_tractor",
        **{"in": "0", "out": str(max(total_frames - 1, 0))},
    )


# --- Audio probing ---


def _probe_audio(audio_path: Path) -> dict | None:
    """Probe an audio file with ffprobe to extract stream metadata.

    Returns a dict with sample_rate, channels, codec_name on success,
    or None if ffprobe is unavailable or the probe fails.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                "-select_streams",
                "a:0",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        logger.debug("ffprobe not found, skipping audio probe")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("ffprobe timed out probing %s", audio_path)
        return None

    if result.returncode != 0:
        logger.debug("ffprobe returned %d for %s", result.returncode, audio_path)
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.debug("ffprobe output not valid JSON for %s", audio_path)
        return None

    streams = data.get("streams", [])
    if not streams:
        logger.debug("No audio streams found in %s", audio_path)
        return None

    stream = streams[0]
    return {
        "sample_rate": stream.get("sample_rate", "48000"),
        "channels": stream.get("channels", 2),
        "codec_name": stream.get("codec_name", "unknown"),
    }


# --- Ken Burns filter ---

# Scale factor for pan/zoom effects (matches ken_burns.py's 1.2x for panning)
_KB_SCALE = 1.2


def _add_ken_burns_filter(
    producer: ET.Element,
    ken_burns: str | None,
    width: int,
    height: int,
    length_frames: int,
) -> None:
    """Add a Kdenlive transform (qtblend) filter for Ken Burns pan/zoom effects.

    The qtblend filter's rect property defines keyframed output rectangles:
    ``frame=x y w h opacity``. Scaling the image beyond the canvas
    dimensions and shifting it creates zoom and pan effects.
    """
    if ken_burns is None or ken_burns == "static":
        return

    last_frame = length_frames - 1
    sw = round(width * _KB_SCALE)
    sh = round(height * _KB_SCALE)
    cx = round((width - sw) / 2)
    cy = round((height - sh) / 2)

    if ken_burns == "zoom_in":
        start = f"0 0 {width} {height} 1"
        end = f"{cx} {cy} {sw} {sh} 1"
    elif ken_burns == "zoom_out":
        start = f"{cx} {cy} {sw} {sh} 1"
        end = f"0 0 {width} {height} 1"
    elif ken_burns == "pan_ltr":
        # Left edge → right edge, vertically centered
        x_end = width - sw
        start = f"0 {cy} {sw} {sh} 1"
        end = f"{x_end} {cy} {sw} {sh} 1"
    elif ken_burns == "pan_rtl":
        # Right edge → left edge, vertically centered
        x_start = width - sw
        start = f"{x_start} {cy} {sw} {sh} 1"
        end = f"0 {cy} {sw} {sh} 1"
    else:
        logger.warning("Unknown ken_burns value %r, skipping filter", ken_burns)
        return

    rect_value = f"0={start};{last_frame}={end}"
    filt = ET.SubElement(producer, "filter")
    _set_prop(filt, "mlt_service", "qtblend")
    _set_prop(filt, "rect", rect_value)


# --- Transition helpers ---


def _add_internal_mix(
    tractor: ET.Element, transition_id: str, a_track: int, b_track: int
) -> None:
    """Add an internal mix transition (always-active audio mixing)."""
    transition = ET.SubElement(tractor, "transition", id=transition_id)
    _set_prop(transition, "a_track", str(a_track))
    _set_prop(transition, "b_track", str(b_track))
    _set_prop(transition, "mlt_service", "mix")
    _set_prop(transition, "internal_added", "237")
    _set_prop(transition, "always_active", "1")
    _set_prop(transition, "accepts_blanks", "1")
    _set_prop(transition, "sum", "1")


def _add_internal_qtblend(
    tractor: ET.Element, transition_id: str, a_track: int, b_track: int
) -> None:
    """Add an internal qtblend transition (always-active video compositing)."""
    transition = ET.SubElement(tractor, "transition", id=transition_id)
    _set_prop(transition, "a_track", str(a_track))
    _set_prop(transition, "b_track", str(b_track))
    _set_prop(transition, "mlt_service", "qtblend")
    _set_prop(transition, "internal_added", "237")
    _set_prop(transition, "always_active", "1")


# --- Utility ---


def _set_prop(element: ET.Element, name: str, value: str) -> None:
    """Add a <property name="...">value</property> child element."""
    prop = ET.SubElement(element, "property", name=name)
    prop.text = value
