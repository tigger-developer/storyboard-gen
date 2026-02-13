# ABOUTME: Command-line interface for storyboard-gen.
# ABOUTME: Subcommands: generate, assemble, validate, list, init.

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from storyboard_gen import __version__
from storyboard_gen.config import ConfigError, load_project
from storyboard_gen.generate import generate_clip, generate_still
from storyboard_gen.ken_burns import apply_ken_burns
from storyboard_gen.assemble import assemble


HELP_EPILOG = """\
workflow:
  1. storyboard-gen init [directory]    Scaffold a new project
  2. Edit project.yaml                  Define scenes, characters, style
  3. Edit .env                          Configure API credentials
  4. storyboard-gen generate --all      Generate stills and clips
  5. storyboard-gen assemble            Merge clips + stills into final video

providers:
  Google    Imagen (stills) + Veo (clips) — default provider
            Auth: GEMINI_API_KEY or USE_VERTEX=true with GCP credentials
  FAL.ai    Flux models (stills only)
            Auth: FAL_KEY
  Replicate Flux models (stills only)
            Auth: REPLICATE_API_TOKEN
  Configure in project.yaml 'providers' section or per-scene overrides.
  Credentials go in .env in your project directory.

project layout:
  project.yaml    Storyboard definition (scenes, characters, style)
  .env            API credentials (not committed)
  references/     Character/style reference images
  output/         Generated stills, clips, and assembled video

Use 'storyboard-gen <command> --help' for command-specific options.
"""


def main(argv: list[str] | None = None) -> int:
    """Main entry point for storyboard-gen CLI.

    Args:
        argv: Command-line arguments. Defaults to sys.argv[1:].

    Returns:
        Exit code (0 for success, 1 for error).
    """
    if argv is None:
        import sys

        argv = sys.argv[1:]

    # Handle --version / -V before argparse requires a subcommand
    if argv in (["-V"], ["--version"]):
        print(f"storyboard-gen {__version__}")
        return 0

    parser = argparse.ArgumentParser(
        prog="storyboard-gen",
        description=(
            "Generate AI video storyboards. Define scenes in project.yaml, "
            "generate stills and video clips via AI providers, apply Ken Burns "
            "effects, and assemble everything into a final video."
        ),
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate subcommand
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate stills and video clips from scene prompts",
        description="Generate AI stills (images) and video clips for scenes defined in project.yaml.",
        epilog=(
            "examples:\n"
            "  storyboard-gen generate --scene 1        Generate scene 1\n"
            "  storyboard-gen generate --scene 1 5 3    Generate scenes 1, 5, 3 in that order\n"
            "  storyboard-gen generate --all-stills     Generate all still scenes\n"
            "  storyboard-gen generate --all            Generate all stills and clips"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    gen_group = gen_parser.add_mutually_exclusive_group(required=True)
    gen_group.add_argument(
        "--scene", type=int, nargs="+", metavar="N", help="Generate scene(s) by number"
    )
    gen_group.add_argument(
        "--all-stills", action="store_true", help="Generate all stills"
    )
    gen_group.add_argument(
        "--all-clips", action="store_true", help="Generate all video clips"
    )
    gen_group.add_argument("--all", action="store_true", help="Generate everything")

    # assemble subcommand
    asm_parser = subparsers.add_parser(
        "assemble",
        help="Merge generated stills and clips into a final video",
        description=(
            "Apply Ken Burns effects (zoom, pan) to stills, then merge all "
            "stills and video clips in scene order into a single final video. "
            "Overlays audio from audio.m4a if present (use --preview to skip)."
        ),
        epilog=(
            "examples:\n"
            "  storyboard-gen assemble                  Assemble with audio\n"
            "  storyboard-gen assemble --preview        Assemble without audio\n"
            "  storyboard-gen assemble --output out.mp4 Custom output filename"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    asm_parser.add_argument(
        "--preview", action="store_true", help="Assemble without audio"
    )
    asm_parser.add_argument(
        "--output", type=str, default="assembled.mp4", help="Output filename"
    )

    # validate subcommand
    subparsers.add_parser(
        "validate",
        help="Validate project.yaml and show summary",
        description="Parse and validate project.yaml, reporting any errors. Shows project summary on success.",
    )

    # list subcommand
    subparsers.add_parser(
        "list",
        help="List all scenes with type, duration, and Ken Burns effect",
        description="Display a table of all scenes with their type, duration, Ken Burns effect, and title.",
    )

    # init subcommand
    init_parser = subparsers.add_parser(
        "init",
        help="Scaffold a new project with template files",
        description=(
            "Create a new storyboard project directory with template "
            "project.yaml, .env, .gitignore, and references/ directory."
        ),
        epilog=(
            "examples:\n"
            "  storyboard-gen init                  Scaffold in current directory\n"
            "  storyboard-gen init ~/Movies/my-vid  Scaffold in a named directory"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init_parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to create project in (default: current directory)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Load .env from cwd so all provider credentials are available
    load_dotenv(Path.cwd() / ".env")

    try:
        return _dispatch(args)
    except ConfigError as e:
        logging.error("Configuration error: %s", e)
        return 1
    except KeyboardInterrupt:
        logging.info("Interrupted")
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    """Dispatch to the appropriate subcommand handler."""
    if args.command == "validate":
        return _cmd_validate()
    if args.command == "list":
        return _cmd_list()
    if args.command == "generate":
        return _cmd_generate(args)
    if args.command == "assemble":
        return _cmd_assemble(args)
    if args.command == "init":
        return _cmd_init(args)
    return 1


def _cmd_validate() -> int:
    """Validate project.yaml and report any issues."""
    project = load_project()
    print(f"Project: {project.title}")
    print(f"Aspect ratio: {project.aspect_ratio}")
    print(f"Characters: {len(project.characters)}")
    print(
        f"Scenes: {len(project.scenes)} ({len(project.get_stills())} stills, {len(project.get_clips())} clips)"
    )
    print("Valid.")
    return 0


def _cmd_list() -> int:
    """List all scenes with their details."""
    project = load_project()
    print(f"{'#':>3}  {'Type':<6}  {'Dur':>3}s  {'Ken Burns':<10}  Title")
    print("-" * 60)
    for scene in project.scenes:
        kb = scene.ken_burns or "-"
        print(
            f"{scene.number:>3}  {scene.scene_type:<6}  {scene.duration:>3}s  {kb:<10}  {scene.title}"
        )
    total = sum(s.duration for s in project.scenes)
    print(f"\nTotal duration: ~{total}s")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    """Generate stills and/or clips."""
    project = load_project()
    output_dir = Path.cwd() / "output"

    if args.scene:
        for scene_num in args.scene:
            scene = project.get_scene(scene_num)
            if scene.scene_type == "still":
                generate_still(scene, project, output_dir)
            else:
                generate_clip(scene, project, output_dir)
    elif args.all_stills:
        stills = project.get_stills()
        print(f"Generating {len(stills)} stills...")
        for scene in stills:
            generate_still(scene, project, output_dir)
    elif args.all_clips:
        clips = project.get_clips()
        print(f"Generating {len(clips)} clips...")
        for scene in clips:
            generate_clip(scene, project, output_dir)
    elif args.all:
        stills = project.get_stills()
        clips = project.get_clips()
        print(f"Generating {len(stills)} stills and {len(clips)} clips...")
        for scene in stills:
            generate_still(scene, project, output_dir)
        for scene in clips:
            generate_clip(scene, project, output_dir)

    return 0


def _cmd_assemble(args: argparse.Namespace) -> int:
    """Apply Ken Burns effects and assemble final video."""
    project = load_project()
    output_dir = Path.cwd() / "output"

    # Apply Ken Burns to all stills
    for scene in project.get_stills():
        image_path = output_dir / "stills" / f"scene_{scene.number:02d}.png"
        if not image_path.exists():
            logging.error("Missing still for scene %d: %s", scene.number, image_path)
            return 1
        apply_ken_burns(image_path, scene, project.aspect_ratio, output_dir)

    # Assemble
    assemble(project, output_dir, args.output)
    return 0


_TEMPLATE_PROJECT_YAML = """\
title: "My Project"
aspect_ratio: "9:16"

# Uncomment and configure a provider (defaults to Google if omitted)
# providers:
#   still:
#     backend: google            # google, fal, or replicate
#     model: "imagen-4.0-generate-001"
#     options: {}
#   clip:
#     backend: google
#     model: "veo-3.1-fast-generate-001"
#     options: {}

style_prefix: >
  Describe your visual style here. Be specific: art style, colour
  palette, lighting, setting details. This is prepended to every
  scene prompt for consistency.

characters:
  character_one:
    description: >
      Physical description for prompt consistency. Include clothing,
      hair, distinguishing features.
    reference: "references/character_one.jpg"

  character_two:
    description: >
      Another character. Set reference to null if no reference image.
    reference: null

scenes:
  # === ACT 1 ===

  - number: 1
    title: "Opening shot"
    camera: "WIDE"
    type: still
    duration: 8
    ken_burns: "zoom_in"
    characters: [character_one]
    prompt: >
      Describe the opening scene. Include character positions,
      expressions, background, lighting, mood.

  - number: 2
    title: "Second scene"
    camera: "CLOSE"
    type: still
    duration: 6
    ken_burns: "pan_ltr"
    characters: [character_one, character_two]
    prompt: >
      Describe the second scene in detail.

  - number: 3
    title: "Action sequence"
    camera: "WIDE"
    type: clip
    duration: 7
    characters: [character_one, character_two]
    prompt: >
      Clips generate video — describe the motion and action
      you want. Ken Burns is not used for clips.
"""

_TEMPLATE_ENV = """\
# Google Vertex AI backend (recommended if you have a GCP project)
USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_OUTPUT_BUCKET=gs://your-bucket/

# OR Google Gemini Developer API backend (simpler setup)
# GEMINI_API_KEY=your-api-key

# FAL.ai backend (for Flux models)
# FAL_KEY=your-fal-key

# Replicate backend (for Flux models)
# REPLICATE_API_TOKEN=your-replicate-token
"""

_TEMPLATE_GITIGNORE = """\
.env
output/
"""


def _cmd_init(args: argparse.Namespace) -> int:
    """Create a new storyboard project with template files."""
    target = Path(args.directory).resolve()
    target.mkdir(parents=True, exist_ok=True)

    project_yaml = target / "project.yaml"
    if project_yaml.exists():
        logging.error("project.yaml already exists in %s", target)
        return 1

    project_yaml.write_text(_TEMPLATE_PROJECT_YAML)
    (target / ".env").write_text(_TEMPLATE_ENV)
    (target / ".gitignore").write_text(_TEMPLATE_GITIGNORE)
    (target / "references").mkdir(exist_ok=True)

    print(f"Created new project in {target}/")
    print("  project.yaml  — storyboard definition")
    print("  .env          — API credentials (edit before use)")
    print("  .gitignore    — excludes .env and output/")
    print("  references/   — add character/style reference images here")
    return 0
