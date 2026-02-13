# ABOUTME: Kdenlive project file generator for storyboard-gen.
# ABOUTME: Exports an MLT XML project for timeline editing with dissolve transitions.

import logging
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


def _build_mlt(
    project: Project,
    output_dir: Path,
    dissolve_frames: int,
    fps: int,
    audio_path: Path | None,
) -> ET.Element:
    """Build the MLT XML document.

    Returns the root <mlt> Element.
    """
    mlt = ET.Element("mlt")

    # Profile
    aspect_ratio = project.aspect_ratio
    width, height = ASPECT_DIMENSIONS.get(aspect_ratio, (1920, 1080))
    _add_profile(mlt, width, height, fps, aspect_ratio)

    # Scene producers
    producers = []
    for scene in project.scenes:
        clip_path = _resolve_clip_path(scene, output_dir)
        length = _frames(scene.duration, fps)
        producer_id = f"producer_{scene.number}"
        _add_producer(mlt, producer_id, clip_path.resolve(), length)
        producers.append((producer_id, length))

    # Audio producer
    audio_producer_id = None
    if audio_path is not None:
        audio_producer_id = "audio_producer"
        _add_producer(mlt, audio_producer_id, audio_path.resolve(), 0)

    # Build playlists and transitions
    use_dissolves = dissolve_frames > 0 and len(producers) > 1
    if use_dissolves:
        playlists, transitions = _build_playlists_with_dissolves(
            mlt, producers, dissolve_frames
        )
    else:
        playlists = _build_playlist_no_dissolves(mlt, producers)
        transitions = []

    # Audio playlist
    audio_playlist_id = None
    if audio_producer_id:
        audio_playlist = ET.SubElement(mlt, "playlist", id="audio_playlist")
        ET.SubElement(audio_playlist, "entry", producer=audio_producer_id)
        audio_playlist_id = "audio_playlist"

    # Tractor
    _add_tractor(mlt, playlists, transitions, audio_playlist_id)

    return mlt


def _add_profile(
    mlt: ET.Element, width: int, height: int, fps: int, aspect_ratio: str
) -> None:
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
    )


def _add_producer(
    mlt: ET.Element, producer_id: str, path: Path, length_frames: int
) -> None:
    """Add a <producer> element for a clip or audio file."""
    producer = ET.SubElement(mlt, "producer", id=producer_id)
    prop_resource = ET.SubElement(producer, "property", name="resource")
    prop_resource.text = str(path)
    if length_frames > 0:
        prop_length = ET.SubElement(producer, "property", name="length")
        prop_length.text = str(length_frames)


def _build_playlists_with_dissolves(
    mlt: ET.Element,
    producers: list[tuple[str, int]],
    dissolve_frames: int,
) -> tuple[list[str], list[dict]]:
    """Build two alternating playlists (A/B editing) for dissolve transitions.

    Clips alternate between playlist0 and playlist1. Blank entries fill the
    gaps so the timelines stay aligned. Transitions overlap at dissolve points.

    Returns:
        Tuple of (playlist_ids, transition_defs).
    """
    playlist0 = ET.SubElement(mlt, "playlist", id="playlist0")
    playlist1 = ET.SubElement(mlt, "playlist", id="playlist1")

    transitions = []
    timeline_pos = 0  # current position in frames on the timeline

    for i, (producer_id, length) in enumerate(producers):
        is_even = i % 2 == 0
        active_playlist = playlist0 if is_even else playlist1
        other_playlist = playlist1 if is_even else playlist0

        if i == 0:
            # First clip: just place it on playlist0
            ET.SubElement(active_playlist, "entry", producer=producer_id)
            # Other playlist gets a blank for the non-overlapping portion
            blank_length = length - dissolve_frames
            ET.SubElement(other_playlist, "blank", length=str(blank_length))
            timeline_pos = length
        else:
            # Overlap: this clip starts dissolve_frames before previous clip ends
            overlap_start = timeline_pos - dissolve_frames

            # The active playlist needs a blank from its last entry to the
            # start of this clip (accounting for the overlap)
            # For even playlists: last entry ended at some point, gap until now
            # The blank fills the gap between the end of the last entry on
            # this playlist and the start of this entry
            if i >= 2:
                # This playlist had a clip 2 positions ago; calculate the
                # blank needed between end of that clip and start of this one
                prev_same_idx = i - 2
                gap_frames = 0
                for j in range(prev_same_idx + 1, i):
                    gap_frames += producers[j][1] - dissolve_frames
                blank_length = gap_frames - dissolve_frames
                if blank_length > 0:
                    ET.SubElement(active_playlist, "blank", length=str(blank_length))

            ET.SubElement(active_playlist, "entry", producer=producer_id)

            # Add dissolve transition
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

    # Pad the shorter playlist to match timeline length
    # (handled implicitly by Kdenlive)

    return (["playlist0", "playlist1"], transitions)


def _build_playlist_no_dissolves(
    mlt: ET.Element, producers: list[tuple[str, int]]
) -> list[str]:
    """Build a single sequential playlist with no transitions."""
    playlist = ET.SubElement(mlt, "playlist", id="playlist0")
    for producer_id, _length in producers:
        ET.SubElement(playlist, "entry", producer=producer_id)
    return ["playlist0"]


def _add_tractor(
    mlt: ET.Element,
    playlists: list[str],
    transitions: list[dict],
    audio_playlist_id: str | None,
) -> None:
    """Add a <tractor> element combining tracks and transitions."""
    tractor = ET.SubElement(mlt, "tractor", id="tractor0")

    # Add multitrack with references to playlists
    multitrack = ET.SubElement(tractor, "multitrack")
    for playlist_id in playlists:
        ET.SubElement(multitrack, "track", producer=playlist_id)
    if audio_playlist_id:
        ET.SubElement(multitrack, "track", producer=audio_playlist_id)

    # Add transitions (video dissolve + audio crossfade for each)
    for t in transitions:
        # Video dissolve (luma)
        dissolve = ET.SubElement(
            tractor,
            "transition",
            id=f"dissolve_{t['index']}",
        )
        dissolve.set("in", t["in"])
        dissolve.set("out", t["out"])
        prop_mlt_service = ET.SubElement(dissolve, "property", name="mlt_service")
        prop_mlt_service.text = "luma"
        prop_a = ET.SubElement(dissolve, "property", name="a_track")
        prop_a.text = t["a_track"]
        prop_b = ET.SubElement(dissolve, "property", name="b_track")
        prop_b.text = t["b_track"]
        prop_length = ET.SubElement(dissolve, "property", name="length")
        prop_length.text = str(int(t["out"]) - int(t["in"]))

        # Audio crossfade (mix)
        mix = ET.SubElement(
            tractor,
            "transition",
            id=f"mix_{t['index']}",
        )
        mix.set("in", t["in"])
        mix.set("out", t["out"])
        prop_mlt_service = ET.SubElement(mix, "property", name="mlt_service")
        prop_mlt_service.text = "mix"
        prop_a = ET.SubElement(mix, "property", name="a_track")
        prop_a.text = t["a_track"]
        prop_b = ET.SubElement(mix, "property", name="b_track")
        prop_b.text = t["b_track"]
