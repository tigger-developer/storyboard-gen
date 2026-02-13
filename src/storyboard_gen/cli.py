# ABOUTME: Command-line interface for storyboard-gen.
# ABOUTME: Subcommands: generate, assemble, validate, list, init.

import argparse
import logging
from pathlib import Path

from storyboard_gen import __version__
from storyboard_gen.config import ConfigError, load_project
from storyboard_gen.generate import generate_clip, generate_still
from storyboard_gen.ken_burns import apply_ken_burns
from storyboard_gen.assemble import assemble


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
        description="Generate video assets from a YAML storyboard",
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
        "generate", help="Generate images and video clips"
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
    asm_parser = subparsers.add_parser("assemble", help="Assemble final video")
    asm_parser.add_argument(
        "--preview", action="store_true", help="Assemble without audio"
    )
    asm_parser.add_argument(
        "--output", type=str, default="assembled.mp4", help="Output filename"
    )

    # validate subcommand
    subparsers.add_parser("validate", help="Validate project.yaml")

    # list subcommand
    subparsers.add_parser("list", help="List all scenes")

    # init subcommand
    init_parser = subparsers.add_parser("init", help="Create a new project")
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
