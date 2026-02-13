# ABOUTME: Kdenlive project file generator for storyboard-gen.
# ABOUTME: Exports an MLT XML project for timeline editing with dissolve transitions.

import logging
import uuid
import xml.dom.minidom
import xml.etree.ElementTree as ET
from pathlib import Path

from storyboard_gen.ken_burns import ASPECT_DIMENSIONS
from storyboard_gen.models import Project, Scene

logger = logging.getLogger(__name__)


def generate_kdenlive(
    project: Project,
    output_dir: Path,
    output_filename: str | None = None,
    dissolve_frames: int = 15,
    audio_path: Path | None = None,
    fps: int = 30,
) -> Path:
    """Generate a Kdenlive project file (.kdenlive) from a storyboard project.

    Args:
        project: The project definition.
        output_dir: Base output directory (contains stills/, clips/, intermediate/).
        output_filename: Custom output filename. Defaults to "{title}.kdenlive".
        dissolve_frames: Number of frames for dissolve transitions (0 = no dissolves).
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

    mlt = _build_mlt(project, output_dir, dissolve_frames, fps, audio_path)

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
    return int(seconds * fps)


def _resolve_clip_path(scene: Scene, output_dir: Path) -> Path:
    """Resolve the clip path for a scene.

    Stills use the Ken Burns intermediate output; clips use clips/ directly.
    """
    if scene.scene_type == "still":
        return output_dir / "intermediate" / f"scene_{scene.number:02d}.mp4"
    return output_dir / "clips" / f"scene_{scene.number:02d}.mp4"


# ProducerInfo: (producer_id, length_frames, kdenlive_id, clip_name)
ProducerInfo = tuple[str, int, int, str]


def _build_mlt(
    project: Project,
    output_dir: Path,
    dissolve_frames: int,
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
    for scene in project.scenes:
        clip_path = _resolve_clip_path(scene, output_dir)
        length = _frames(scene.duration, fps)
        producer_id = f"producer_{scene.number}"
        _add_scene_producer(
            mlt, producer_id, clip_path.resolve(), length, kdenlive_id, scene.title
        )
        producers.append((producer_id, length, kdenlive_id, scene.title))
        kdenlive_id += 1

    # Audio producer
    audio_info: ProducerInfo | None = None
    if audio_path is not None:
        _add_scene_producer(
            mlt, "audio_producer", audio_path.resolve(), 0, kdenlive_id, "Audio"
        )
        audio_info = ("audio_producer", 0, kdenlive_id, "Audio")
        kdenlive_id += 1

    # Video track: A/B playlists wrapped in a tractor
    use_dissolves = dissolve_frames > 0 and len(producers) > 1
    if use_dissolves:
        _build_video_track_with_dissolves(mlt, producers, dissolve_frames)
    else:
        _build_video_track_no_dissolves(mlt, producers)

    # Audio track (if configured)
    has_audio = audio_info is not None
    if has_audio:
        _build_audio_track(mlt, audio_info)

    # Total timeline length in frames
    if use_dissolves:
        total_frames = sum(p[1] for p in producers) - (
            (len(producers) - 1) * dissolve_frames
        )
    else:
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
) -> None:
    """Add a <producer> element for a scene clip or audio file."""
    attrs = {"id": producer_id}
    if length_frames > 0:
        attrs["in"] = "0"
        attrs["out"] = str(length_frames - 1)
    producer = ET.SubElement(mlt, "producer", **attrs)
    _set_prop(producer, "resource", str(path))
    if length_frames > 0:
        _set_prop(producer, "length", str(length_frames))
    _set_prop(producer, "kdenlive:id", str(kdenlive_id))
    _set_prop(producer, "kdenlive:clipname", clip_name)


def _build_video_track_with_dissolves(
    mlt: ET.Element,
    producers: list[ProducerInfo],
    dissolve_frames: int,
) -> None:
    """Build A/B video playlists and wrap them in a video track tractor.

    Clips alternate between playlist0 and playlist1. During a dissolve,
    clip N (ending on A) overlaps with clip N+1 (starting on B). A luma
    transition handles the video crossfade, a mix transition handles audio.
    """
    playlist0 = ET.SubElement(mlt, "playlist", id="playlist0")
    playlist1 = ET.SubElement(mlt, "playlist", id="playlist1")

    transitions = []
    timeline_pos = 0

    for i, (producer_id, length, kdenlive_id, _name) in enumerate(producers):
        is_even = i % 2 == 0
        active_playlist = playlist0 if is_even else playlist1
        other_playlist = playlist1 if is_even else playlist0

        if i == 0:
            entry = ET.SubElement(
                active_playlist,
                "entry",
                producer=producer_id,
                **{"in": "0", "out": str(length - 1)},
            )
            _set_prop(entry, "kdenlive:id", str(kdenlive_id))
            blank_length = length - dissolve_frames
            ET.SubElement(other_playlist, "blank", length=str(blank_length))
            timeline_pos = length
        else:
            overlap_start = timeline_pos - dissolve_frames

            if i >= 2:
                # Blank between the end of the last clip on this playlist
                # and the start of this one
                prev_same_idx = i - 2
                gap_frames = 0
                for j in range(prev_same_idx + 1, i):
                    gap_frames += producers[j][1] - dissolve_frames
                blank_length = gap_frames - dissolve_frames
                if blank_length > 0:
                    ET.SubElement(active_playlist, "blank", length=str(blank_length))

            entry = ET.SubElement(
                active_playlist,
                "entry",
                producer=producer_id,
                **{"in": "0", "out": str(length - 1)},
            )
            _set_prop(entry, "kdenlive:id", str(kdenlive_id))

            transitions.append(
                {
                    "a_track": "0" if is_even else "1",
                    "b_track": "1" if is_even else "0",
                    "in": str(overlap_start),
                    "out": str(overlap_start + dissolve_frames),
                    "index": i - 1,
                }
            )

            timeline_pos = overlap_start + length

    # Video track tractor wrapping the A/B playlists
    tractor = ET.SubElement(mlt, "tractor", id="video_tractor")
    ET.SubElement(tractor, "track", hide="audio", producer="playlist0")
    ET.SubElement(tractor, "track", hide="audio", producer="playlist1")

    for t in transitions:
        _add_dissolve_transition(tractor, t)
        _add_mix_transition(tractor, t)


def _build_video_track_no_dissolves(
    mlt: ET.Element, producers: list[ProducerInfo]
) -> None:
    """Build sequential video playlists (no transitions) wrapped in a tractor."""
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


# --- Transition helpers ---


def _add_dissolve_transition(tractor: ET.Element, t: dict) -> None:
    """Add a luma (video dissolve) transition to a tractor."""
    dissolve = ET.SubElement(tractor, "transition", id=f"dissolve_{t['index']}")
    dissolve.set("in", t["in"])
    dissolve.set("out", t["out"])
    _set_prop(dissolve, "mlt_service", "luma")
    _set_prop(dissolve, "a_track", t["a_track"])
    _set_prop(dissolve, "b_track", t["b_track"])
    _set_prop(dissolve, "length", str(int(t["out"]) - int(t["in"])))


def _add_mix_transition(tractor: ET.Element, t: dict) -> None:
    """Add a mix (audio crossfade) transition to a tractor."""
    mix = ET.SubElement(tractor, "transition", id=f"mix_{t['index']}")
    mix.set("in", t["in"])
    mix.set("out", t["out"])
    _set_prop(mix, "mlt_service", "mix")
    _set_prop(mix, "a_track", t["a_track"])
    _set_prop(mix, "b_track", t["b_track"])


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
