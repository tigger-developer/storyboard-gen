# ABOUTME: Command-line interface for storyboard-gen.
# ABOUTME: Subcommands: generate, assemble, kdenlive, validate, list, init, schema.

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from storyboard_gen import __version__
from storyboard_gen.config import ConfigError, load_project
from storyboard_gen.generate import (
    check_reference_warnings,
    generate_clip,
    generate_still,
    resolve_provider_config,
)
from storyboard_gen.ken_burns import apply_ken_burns
from storyboard_gen.assemble import assemble
from storyboard_gen.kdenlive import generate_kdenlive
from storyboard_gen.models import CAMERA_PROMPTS, format_scene_number


HELP_EPILOG = """\
workflow:
  1. storyboard-gen init [directory]    Scaffold a new project
  2. Edit project.yaml                  Define scenes, characters, style
  3. Edit .env                          Configure API credentials
  4. storyboard-gen generate --all      Generate stills and clips
  5. storyboard-gen assemble            Merge clips + stills into final video
  6. storyboard-gen kdenlive            Export Kdenlive project for editing

providers:
  Google    Imagen (stills) + Veo (clips) — default provider
            Auth: GEMINI_API_KEY or USE_VERTEX=true with GCP credentials
  FAL.ai    Flux + Kontext models (stills only)
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
            "  storyboard-gen generate --all-clips      Generate all video clips\n"
            "  storyboard-gen generate --all            Generate all stills and clips"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    gen_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be sent to the API without generating",
    )
    gen_group = gen_parser.add_mutually_exclusive_group(required=True)
    gen_group.add_argument(
        "--scene", type=str, nargs="+", metavar="N", help="Generate scene(s) by number"
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
            "Muxes audio if configured in project.yaml or via --audio."
        ),
        epilog=(
            "examples:\n"
            "  storyboard-gen assemble                      Assemble (with audio if configured)\n"
            "  storyboard-gen assemble --preview             Assemble without audio\n"
            "  storyboard-gen assemble --audio narration.m4a Override audio track\n"
            "  storyboard-gen assemble --output out.mp4      Custom output filename"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    asm_parser.add_argument(
        "--preview", action="store_true", help="Assemble without audio"
    )
    asm_parser.add_argument(
        "--audio",
        type=str,
        default=None,
        help="Audio file to mux (overrides project.yaml)",
    )
    asm_parser.add_argument(
        "--output", type=str, default="assembled.mp4", help="Output filename"
    )

    # kdenlive subcommand
    kdenlive_parser = subparsers.add_parser(
        "kdenlive",
        help="Export a Kdenlive project for timeline editing",
        description=(
            "Generate a Kdenlive (.kdenlive) project file from the storyboard. "
            "Includes Ken Burns transform effects on stills and an audio track if "
            "configured. Open the result in Kdenlive for fine-tuning."
        ),
        epilog=(
            "examples:\n"
            "  storyboard-gen kdenlive                              Export with Ken Burns effects\n"
            "  storyboard-gen kdenlive --output my_project.kdenlive Custom output name\n"
            "  storyboard-gen kdenlive --preview                    Export without audio"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    kdenlive_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output filename (default: {title}.kdenlive)",
    )
    kdenlive_parser.add_argument(
        "--audio",
        type=str,
        default=None,
        help="Audio file to include (overrides project.yaml)",
    )
    kdenlive_parser.add_argument(
        "--preview",
        action="store_true",
        help="Export without audio",
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

    # schema subcommand
    subparsers.add_parser(
        "schema",
        help="Show project.yaml field reference",
        description="Display a complete reference of all project.yaml fields, valid values, and defaults.",
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
    if args.command == "kdenlive":
        return _cmd_kdenlive(args)
    if args.command == "init":
        return _cmd_init(args)
    if args.command == "schema":
        return _cmd_schema()
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
    print(f"{'#':>3}  {'Type':<6}  {'Dur':>5}  {'Ken Burns':<10}  Title")
    print("-" * 62)
    for scene in project.scenes:
        kb = scene.ken_burns or "-"
        dur = f"{scene.duration:g}s"
        print(
            f"{scene.number:>3}  {scene.scene_type:<6}  {dur:>5}  {kb:<10}  {scene.title}"
        )
    total = sum(s.duration for s in project.scenes)
    print(f"\nTotal duration: ~{total:g}s")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    """Generate stills and/or clips."""
    project = load_project()
    project_dir = Path.cwd()
    output_dir = project_dir / "output"

    # Collect target scenes
    scenes = []
    if args.scene:
        scenes = [project.get_scene(n) for n in args.scene]
    elif args.all_stills:
        scenes = project.get_stills()
    elif args.all_clips:
        scenes = project.get_clips()
    elif args.all:
        scenes = list(project.scenes)

    if args.dry_run:
        return _dry_run(project, scenes)

    if not args.scene:
        stills = [s for s in scenes if s.scene_type == "still"]
        clips = [s for s in scenes if s.scene_type == "clip"]
        if stills and clips:
            print(f"Generating {len(stills)} stills and {len(clips)} clips...")
        elif stills:
            print(f"Generating {len(stills)} stills...")
        elif clips:
            print(f"Generating {len(clips)} clips...")

    for scene in scenes:
        # Show reference/model mismatch warnings (#62)
        provider_cfg = resolve_provider_config(scene, project, scene.scene_type)
        check_reference_warnings(scene, project, provider_cfg)

        if scene.scene_type == "still":
            generate_still(scene, project, output_dir, project_dir=project_dir)
        else:
            generate_clip(scene, project, output_dir, project_dir=project_dir)

    return 0


def _dry_run(project, scenes) -> int:
    """Print what would be sent to the API for each scene."""
    for i, scene in enumerate(scenes):
        if i > 0:
            print()

        provider_cfg = resolve_provider_config(scene, project, scene.scene_type)
        prompt = project.build_prompt(scene)
        refs = project.get_reference_images(scene)

        print(f"Scene {scene.number}: {scene.title}")
        print(f"  Type:       {scene.scene_type}")
        print(f"  Duration:   {scene.duration:g}s")
        if scene.camera:
            print(f"  Camera:     {scene.camera}")
        if scene.ken_burns:
            print(f"  Ken Burns:  {scene.ken_burns}")
        print(f"  Provider:   {provider_cfg.backend} / {provider_cfg.model}")
        if provider_cfg.options:
            print(f"  Options:    {provider_cfg.options}")
        if refs:
            print("  References:")
            for ref in refs:
                status = "ok" if ref.exists() else "MISSING"
                print(f"    [{status}] {ref}")
        if project.style_reference:
            print("  Style references:")
            for ref in project.style_reference:
                status = "ok" if ref.exists() else "MISSING"
                print(f"    [{status}] {ref}")
        print("  Prompt:")
        print(f"    {prompt}")

        # Show reference/model mismatch warnings (#62)
        warns = check_reference_warnings(scene, project, provider_cfg)
        for w in warns:
            print(f"  WARNING: {w}")

    return 0


def _cmd_assemble(args: argparse.Namespace) -> int:
    """Apply Ken Burns effects and assemble final video."""
    project = load_project()
    output_dir = Path.cwd() / "output"

    # Apply Ken Burns to all stills
    for scene in project.get_stills():
        image_path = (
            output_dir / "stills" / f"scene_{format_scene_number(scene.number)}.png"
        )
        if not image_path.exists():
            logging.error("Missing still for scene %s: %s", scene.number, image_path)
            return 1
        apply_ken_burns(image_path, scene, project.aspect_ratio, output_dir)

    # Resolve audio: --preview → None; --audio → override; project.yaml → default
    audio_path = None
    if not args.preview:
        if args.audio:
            audio_path = Path(args.audio).resolve()
        elif project.audio:
            audio_path = project.audio

        if audio_path and not audio_path.exists():
            logging.warning(
                "Audio file not found: %s — assembling without audio", audio_path
            )
            audio_path = None

    # Assemble
    assemble(project, output_dir, args.output, audio_path=audio_path)
    return 0


def _cmd_kdenlive(args: argparse.Namespace) -> int:
    """Export a Kdenlive project file for timeline editing."""
    project = load_project()
    output_dir = Path.cwd() / "output"

    # Resolve audio: --preview → None; --audio → override; project.yaml → default
    audio_path = None
    if not args.preview:
        if args.audio:
            audio_path = Path(args.audio).resolve()
        elif project.audio:
            audio_path = project.audio

        if audio_path and not audio_path.exists():
            logging.warning(
                "Audio file not found: %s — exporting without audio", audio_path
            )
            audio_path = None

    output_path = generate_kdenlive(
        project,
        output_dir,
        output_filename=args.output,
        audio_path=audio_path,
    )
    print(f"Kdenlive project: {output_path}")
    return 0


def _cmd_schema() -> int:
    """Print the complete project.yaml field reference."""
    # Build camera table from CAMERA_PROMPTS (stays in sync automatically)
    camera_lines = []
    for key in [
        "EWS",
        "WIDE",
        "MEDIUM",
        "MCU",
        "CLOSE",
        "ECU",
        "POV",
        "LOW",
        "HIGH",
        "OVERHEAD",
        "OTS",
        "DUTCH",
    ]:
        camera_lines.append(f"    {key:<10} {CAMERA_PROMPTS[key]}")
    camera_table = "\n".join(camera_lines)

    print(f"""\
project.yaml field reference (storyboard-gen {__version__})
{"=" * 56}

TOP-LEVEL FIELDS
  title           (string, required)  Project title.
  aspect_ratio    (string)            Output ratio. Default: "16:9".
                                      Values: 9:16, 16:9, 4:3, 1:1
  audio           (string)            Audio file path, relative to project dir.
                                      Muxed into assembled video.
  style_prefix    (string)            Visual style prepended to every prompt.
  style_reference (list)              Style reference image paths for Ideogram Character.
                                      Only used by fal-ai/ideogram/character.
  providers       (object)            AI provider config (see below).
  characters      (object)            Named characters (see below).
  scenes          (list, required)    Scene definitions (see below).

PROVIDERS
  Configured under providers.still and providers.clip.
  If omitted, defaults to Google (Imagen for stills, Veo for clips).

  Fields per provider:
    backend       (string, required)  google, fal, or replicate
    model         (string, required)  Provider-specific model ID
    options       (object)            Provider-specific options

  Google models:    imagen-4.0-generate-001 (still), veo-3.1-fast-generate-001 (clip)
  FAL.ai stills:    fal-ai/flux-general, fal-ai/flux-2, fal-ai/flux-2/turbo, fal-ai/flux-pro/kontext
                    fal-ai/flux-pro/kontext/max/multi (multi-ref), fal-ai/kling-image/o1 (multi-ref)
                    fal-ai/ideogram/character (style + character refs)
  FAL.ai clips:     fal-ai/kling-video/*
  Replicate models: black-forest-labs/flux-1.1-pro, black-forest-labs/flux-dev

CHARACTERS
  Keyed by character ID (used in scene characters lists).

  Fields:
    description   (string)            Physical description for prompt consistency.
    reference     (list)              Reference image paths (relative to project dir).

SCENE FIELDS
  number          (int)               Scene number. Default: auto (1-indexed).
  title           (string)            Human-readable title. Default: "Scene N".
  type            (string)            "still" or "clip". Default: "still".
  prompt          (string)            Scene description for the AI model.
  duration        (number)            Seconds (supports decimals). Default: 5.
  camera          (string)            Camera angle (see values below).
  ken_burns       (string)            Pan/zoom effect for stills (see values below).
  characters      (list)              Character IDs for reference image lookup.
  provider        (object)            Per-scene provider override (same as providers.*).
  model           (string)            Per-scene model override (inherits backend/options).
  reference       (list)              Per-scene reference images (overrides character refs).
  source_frame    (path, clips only)  Image for image-to-video first frame.
  last_frame      (path, clips only)  Interpolation end frame (requires source_frame).
  extend_from     (string, clips only) Scene number to extend from.
  seed            (int)               Reproducibility seed.
  variants        (int)               Number of video takes, 1-4. Default: 1.

CAMERA VALUES
  Injected into AI prompt automatically. Case-insensitive.
  Prompt assembly order: style_prefix -> camera -> characters -> scene prompt.

{camera_table}

KEN BURNS VALUES (stills only)
    zoom_in     Slow zoom into the image.
    zoom_out    Slow zoom out from the image.
    pan_ltr     Pan left to right.
    pan_rtl     Pan right to left.
    static      No movement.
    (omitted)   No Ken Burns processing.""")
    return 0


_TEMPLATE_PROJECT_YAML = """\
title: "My Project"
aspect_ratio: "9:16"

# Optional: audio track to mux into assembled video
# audio: "audio.m4a"

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

# Optional: style reference images for Ideogram Character model
# These are passed as aesthetic/style references (image_urls), separate
# from character references. Only used by fal-ai/ideogram/character.
# style_reference:
#   - "references/style_ref.jpg"

style_prefix: >
  Describe your visual style here. Be specific: art style, colour
  palette, lighting, setting details. This is prepended to every
  scene prompt for consistency.

characters:
  character_one:
    description: >
      Physical description for prompt consistency. Include clothing,
      hair, distinguishing features.
    reference:
      - "references/character_one.jpg"

  character_two:
    description: >
      Another character. Omit reference or use empty list if no
      reference images are available.
    reference: []

scenes:
  # Camera values (injected into AI prompt automatically):
  #   EWS      — extreme wide establishing shot
  #   WIDE     — wide shot, full body in environment
  #   MEDIUM   — waist up
  #   MCU      — chest up (medium close-up)
  #   CLOSE    — face, tightly framed
  #   ECU      — extreme close-up, single detail
  #   POV      — first-person point of view
  #   LOW      — low angle, looking up
  #   HIGH     — high angle, looking down
  #   OVERHEAD — bird's-eye, straight down
  #   OTS      — over-the-shoulder
  #   DUTCH    — tilted camera, unease

  # === ACT 1 ===

  - number: 1
    title: "Opening shot"
    camera: "EWS"
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
    camera: "MEDIUM"
    type: clip
    duration: 7
    characters: [character_one, character_two]
    prompt: >
      Clips generate video — describe the motion and action
      you want. Ken Burns is not used for clips.

  # === PER-SCENE PROVIDER EXAMPLES (uncomment to use) ===

  # Multi-character still with Kling O1 Image:
  # Uses @character_id tokens mapped to @ImageN references.
  # - number: 4
  #   title: "Group portrait (O1 Image)"
  #   camera: "WIDE"
  #   type: still
  #   duration: 5
  #   ken_burns: "static"
  #   characters: [character_one, character_two]
  #   provider:
  #     backend: fal
  #     model: "fal-ai/kling-image/o1"
  #   prompt: >
  #     @character_one and @character_two stand side by side.

  # Multi-character still with Kontext Max Multi:
  # Accepts multiple reference images; model infers associations.
  # No @character_id mapping needed — just describe naturally.
  # - number: 5
  #   title: "Group portrait (Kontext Multi)"
  #   camera: "MEDIUM"
  #   type: still
  #   duration: 5
  #   ken_burns: "zoom_in"
  #   characters: [character_one, character_two]
  #   provider:
  #     backend: fal
  #     model: "fal-ai/flux-pro/kontext/max/multi"
  #   prompt: >
  #     Two characters standing together in a field at sunset.

  # Ideogram Character with separate style + character references:
  # Character refs → reference_image_urls (identity).
  # Style refs → image_urls (aesthetic). Requires style_reference at top level.
  # - number: 6
  #   title: "Portrait (Ideogram Character)"
  #   camera: "CLOSE"
  #   type: still
  #   duration: 5
  #   ken_burns: "static"
  #   characters: [character_one]
  #   provider:
  #     backend: fal
  #     model: "fal-ai/ideogram/character"
  #   prompt: >
  #     A portrait of character_one in a warm studio setting.

  # Multi-character clip with Kling O3 (video):
  # Uses @character_id tokens mapped to @ElementN references.
  # - number: 7
  #   title: "Chase sequence (O3)"
  #   camera: "MEDIUM"
  #   type: clip
  #   duration: 5
  #   characters: [character_one, character_two]
  #   provider:
  #     backend: fal
  #     model: "fal-ai/kling-video/o3/standard/image-to-video"
  #   prompt: >
  #     @character_one chases @character_two through a garden.
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
# Secrets
.env

# Operation logs (crash recovery, not needed in source control)
logs/

# Generated video (large, regenerable from stills + project.yaml)
output/intermediate/
output/clips/

# Assembled video output
*.mp4
*.mov
*.avi
*.mkv
*.webm

# Keep generated stills (expensive API calls to regenerate)
!output/stills/

# Keep Kdenlive project files (small XML)
!*.kdenlive

# macOS
.DS_Store
"""


def init_project(target: Path) -> None:
    """Scaffold a new storyboard project at the given directory.

    Creates project.yaml, .env, .gitignore, README.md, references/, and logs/.
    Reusable by both the CLI and the GUI.

    Args:
        target: Directory to create the project in (created if needed).

    Raises:
        FileExistsError: If project.yaml already exists in the target directory.
    """
    target.mkdir(parents=True, exist_ok=True)

    project_yaml = target / "project.yaml"
    if project_yaml.exists():
        raise FileExistsError(f"project.yaml already exists in {target}")

    # Extract title from template for use in README
    title = "My Project"
    for line in _TEMPLATE_PROJECT_YAML.splitlines():
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip('"').strip("'")
            break

    project_yaml.write_text(_TEMPLATE_PROJECT_YAML)
    (target / ".env").write_text(_TEMPLATE_ENV)
    (target / ".gitignore").write_text(_TEMPLATE_GITIGNORE)
    (target / "README.md").write_text(
        f"# {title}\n"
        "\n"
        "A [storyboard-gen](https://github.com/tigger04/storyboard-gen) project.\n"
        "\n"
        "Edit `project.yaml` to define your scenes, characters, and style,"
        " then run `storyboard-gen generate` to create your assets.\n"
        "\n"
        "See the [project.yaml spec]"
        "(https://github.com/tigger04/storyboard-gen/blob/master/"
        "docs/project-yaml-spec.md) for the full schema reference.\n"
    )
    (target / "references").mkdir(exist_ok=True)
    (target / "logs").mkdir(exist_ok=True)


def _cmd_init(args: argparse.Namespace) -> int:
    """Create a new storyboard project with template files."""
    target = Path(args.directory).resolve()

    try:
        init_project(target)
    except FileExistsError as exc:
        logging.error(str(exc))
        return 1

    print(f"Created new project in {target}/")
    print("  project.yaml  — storyboard definition")
    print("  README.md     — project overview")
    print("  .env          — API credentials (edit before use)")
    print("  .gitignore    — excludes secrets and video, keeps stills and Kdenlive")
    print("  references/   — add character/style reference images here")
    print("  logs/         — operation logs for crash recovery")
    return 0
