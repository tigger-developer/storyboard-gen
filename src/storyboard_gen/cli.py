# ABOUTME: Command-line interface for storyboard-gen.
# ABOUTME: Subcommands: generate, assemble, validate, list.

import argparse
import logging
import sys
from pathlib import Path

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
    parser = argparse.ArgumentParser(
        prog="storyboard-gen",
        description="Generate video assets from a YAML storyboard",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate images and video clips")
    gen_group = gen_parser.add_mutually_exclusive_group(required=True)
    gen_group.add_argument("--scene", type=int, help="Generate a single scene by number")
    gen_group.add_argument("--all-stills", action="store_true", help="Generate all stills")
    gen_group.add_argument("--all-clips", action="store_true", help="Generate all video clips")
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
    return 1


def _cmd_validate() -> int:
    """Validate project.yaml and report any issues."""
    project = load_project()
    print(f"Project: {project.title}")
    print(f"Aspect ratio: {project.aspect_ratio}")
    print(f"Characters: {len(project.characters)}")
    print(f"Scenes: {len(project.scenes)} ({len(project.get_stills())} stills, {len(project.get_clips())} clips)")
    print("Valid.")
    return 0


def _cmd_list() -> int:
    """List all scenes with their details."""
    project = load_project()
    print(f"{'#':>3}  {'Type':<6}  {'Dur':>3}s  {'Ken Burns':<10}  Title")
    print("-" * 60)
    for scene in project.scenes:
        kb = scene.ken_burns or "-"
        print(f"{scene.number:>3}  {scene.scene_type:<6}  {scene.duration:>3}s  {kb:<10}  {scene.title}")
    total = sum(s.duration for s in project.scenes)
    print(f"\nTotal duration: ~{total}s")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    """Generate stills and/or clips."""
    project = load_project()
    output_dir = Path.cwd() / "output"

    if args.scene:
        scene = project.get_scene(args.scene)
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
