# ABOUTME: Ken Burns effect generator for storyboard-gen.
# ABOUTME: Converts still images to short video clips with zoom/pan effects using FFmpeg.

import logging
import subprocess
from pathlib import Path

from storyboard_gen.models import Scene

logger = logging.getLogger(__name__)

# FFmpeg filter expressions for each Ken Burns type.
# These assume the input image is larger than the output frame
# to allow for zooming/panning without black borders.
KEN_BURNS_FILTERS = {
    "zoom_in": (
        "scale=8000:-1,"
        "zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}"
    ),
    "zoom_out": (
        "scale=8000:-1,"
        "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        "d={frames}:s={width}x{height}:fps={fps}"
    ),
    "pan_ltr": (
        "scale=8000:-1,"
        "zoompan=z='1.2':x='(iw-iw/zoom)*on/{frames}':"
        "y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}"
    ),
    "pan_rtl": (
        "scale=8000:-1,"
        "zoompan=z='1.2':x='(iw-iw/zoom)*(1-on/{frames})':"
        "y='ih/2-(ih/zoom/2)':d={frames}:s={width}x{height}:fps={fps}"
    ),
    "static": (
        "scale={width}:{height}:force_original_aspect_ratio=decrease,"
        "pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    ),
}

# Dimensions for supported aspect ratios
ASPECT_DIMENSIONS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "4:3": (1440, 1080),
    "1:1": (1080, 1080),
}


def apply_ken_burns(
    image_path: Path,
    scene: Scene,
    aspect_ratio: str,
    output_dir: Path,
    fps: int = 30,
) -> Path:
    """Apply a Ken Burns effect to a still image, producing a video clip.

    Args:
        image_path: Path to the source PNG image.
        scene: Scene definition (duration and ken_burns type).
        aspect_ratio: Project aspect ratio (e.g. "9:16").
        output_dir: Directory for intermediate output.
        fps: Frames per second for output video.

    Returns:
        Path to the generated MP4 clip.

    Raises:
        FileNotFoundError: If the source image doesn't exist.
        ValueError: If the ken_burns type or aspect ratio is unsupported.
        RuntimeError: If FFmpeg fails.
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    effect = scene.ken_burns or "static"
    if effect not in KEN_BURNS_FILTERS:
        raise ValueError(f"Unsupported Ken Burns effect: {effect}")

    if aspect_ratio not in ASPECT_DIMENSIONS:
        raise ValueError(f"Unsupported aspect ratio: {aspect_ratio}")

    width, height = ASPECT_DIMENSIONS[aspect_ratio]
    frames = scene.duration * fps

    intermediate_dir = output_dir / "intermediate"
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    output_path = intermediate_dir / f"scene_{scene.number:02d}.mp4"

    filter_template = KEN_BURNS_FILTERS[effect]
    vf = filter_template.format(frames=frames, width=width, height=height, fps=fps)

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(image_path),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-t",
        str(scene.duration),
        str(output_path),
    ]

    logger.info(
        "Applying %s to scene %d (%ds at %dfps)",
        effect,
        scene.number,
        scene.duration,
        fps,
    )
    logger.debug("FFmpeg command: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed for scene {scene.number}: {result.stderr}")

    logger.info("Ken Burns output: %s", output_path)
    return output_path
