# ABOUTME: Video assembly for storyboard-gen.
# ABOUTME: Concatenates scene clips into a final video using FFmpeg, with optional audio muxing.

import logging
import subprocess
import tempfile
from pathlib import Path

from storyboard_gen.models import Project

logger = logging.getLogger(__name__)


def assemble(
    project: Project,
    output_dir: Path,
    output_filename: str = "assembled.mp4",
    audio_path: Path | None = None,
) -> Path:
    """Assemble all scene clips into a single video.

    Expects scene clips in output_dir/intermediate/ (from Ken Burns)
    and output_dir/clips/ (video clips). Concatenates in scene order.
    Optionally muxes an audio track.

    Args:
        project: The project definition.
        output_dir: Base output directory.
        output_filename: Name of the final output file.
        audio_path: Optional path to an audio file to mux in.

    Returns:
        Path to the assembled video.

    Raises:
        FileNotFoundError: If expected scene files are missing.
        RuntimeError: If FFmpeg fails.
    """
    final_dir = output_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    output_path = final_dir / output_filename

    clip_paths = []
    for scene in project.scenes:
        if scene.scene_type == "still":
            clip = output_dir / "intermediate" / f"scene_{scene.number:02d}.mp4"
        else:
            clip = output_dir / "clips" / f"scene_{scene.number:02d}.mp4"

        if not clip.exists():
            raise FileNotFoundError(
                f"Missing clip for scene {scene.number} ({scene.title}): {clip}"
            )
        clip_paths.append(clip)

    # Write FFmpeg concat file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as concat_file:
        for clip in clip_paths:
            concat_file.write(f"file '{clip.resolve()}'\n")
        concat_path = concat_file.name

    if audio_path:
        _assemble_with_audio(clip_paths, concat_path, output_path, audio_path)
    else:
        _assemble_without_audio(clip_paths, concat_path, output_path)

    logger.info("Final video: %s", output_path)
    return output_path


def _assemble_without_audio(
    clip_paths: list[Path], concat_path: str, output_path: Path
) -> None:
    """Concatenate clips into a single video without audio."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_path,
        "-c",
        "copy",
        str(output_path),
    ]

    logger.info("Assembling %d scenes into %s", len(clip_paths), output_path)
    result = subprocess.run(cmd, capture_output=True, text=True)

    Path(concat_path).unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg assembly failed: {result.stderr}")


def _assemble_with_audio(
    clip_paths: list[Path],
    concat_path: str,
    output_path: Path,
    audio_path: Path,
) -> None:
    """Concatenate clips, then mux audio into the result."""
    # Step 1: concat to a temp file
    concat_output = output_path.parent / "concat_only.mp4"
    concat_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_path,
        "-c",
        "copy",
        str(concat_output),
    ]

    logger.info("Assembling %d scenes (pass 1: concat)", len(clip_paths))
    result = subprocess.run(concat_cmd, capture_output=True, text=True)

    Path(concat_path).unlink(missing_ok=True)

    if result.returncode != 0:
        concat_output.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg assembly failed: {result.stderr}")

    # Step 2: mux audio
    mux_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(concat_output),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]

    logger.info("Muxing audio from %s (pass 2)", audio_path)
    try:
        result = subprocess.run(mux_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio mux failed: {result.stderr}")
    finally:
        concat_output.unlink(missing_ok=True)
