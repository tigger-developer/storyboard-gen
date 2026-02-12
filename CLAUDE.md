# Claude Code Configuration for storyboard-gen

## Our Relationship

We are coworkers. I'm Taḋg.

### Read and follow:

- Our documentation rules: @~/.claude/docs/DOCUMENTATION.md
- Our coding standards: @~/.claude/docs/CODING.md
- We practice TDD! see: @~/.claude/docs/TESTING.md
- Our git standards: @~/.claude/docs/GIT.md

## What is storyboard-gen?

A CLI tool that generates video stills and clips from a `project.yaml` storyboard definition. It calls Google Vertex AI APIs (Imagen for stills, Veo for video clips) and assembles the results with Ken Burns effects via FFmpeg.

The tool is installed once and run from within any project directory. A project is just a folder containing a `project.yaml` and an optional `references/` directory with character/style reference images.

## Usage

```bash
# From within a project directory (e.g. ~/Movies/social/pout/)
storyboard-gen generate --scene 1       # Generate one scene
storyboard-gen generate --all-stills    # Generate all stills
storyboard-gen generate --all-clips     # Generate all video clips
storyboard-gen generate --all           # Generate everything
storyboard-gen assemble                 # Assemble final video with Ken Burns
storyboard-gen assemble --preview       # Assemble without audio
storyboard-gen validate                 # Validate project.yaml
storyboard-gen list                     # List all scenes with status
```

## Architecture

### Project structure (this repo)

```
storyboard-gen/
├── CLAUDE.md              # This file
├── LICENSE                # MIT, Copyright Taḋg Paul
├── Makefile               # Build, test, install, release entry points
├── README.md              # Project overview and quickstart
├── requirements.txt       # Python dependencies
├── setup.py               # Package installation
├── .env.example           # Template for API credentials
├── .gitignore
├── .python-version        # 3.12
├── docs/
│   ├── VISION.md          # Project vision and goals
│   └── architecture.md    # Technical architecture
├── scripts/
│   └── release.sh         # Release automation (version, tag, Homebrew)
├── src/
│   └── storyboard_gen/
│       ├── __init__.py
│       ├── __main__.py    # python -m storyboard_gen entry point
│       ├── cli.py         # argparse CLI
│       ├── config.py      # Load and validate project.yaml
│       ├── models.py      # Dataclasses: Project, Scene, Character
│       ├── client.py      # Google GenAI client setup
│       ├── generate.py    # Image and video generation
│       ├── ken_burns.py   # Ken Burns effects via FFmpeg
│       └── assemble.py    # Final video assembly via FFmpeg
└── tests/
    ├── __init__.py
    ├── conftest.py        # Shared fixtures (sample project.yaml, etc.)
    ├── test_config.py
    ├── test_models.py
    ├── test_generate.py
    └── test_cli.py
```

### Per-project structure (created by users)

```
some-project/
├── project.yaml           # Storyboard definition (THE key file)
├── .env                   # API credentials (not committed)
├── references/            # Character/style reference images
│   ├── boy.jpg            # jpg, png, or other image formats
│   └── brow_man.png
├── audio.m4a              # Optional voice-over/soundtrack for assembly
└── output/                # Generated assets (created by tool)
    ├── stills/
    ├── clips/
    ├── intermediate/      # Ken Burns output from stills
    └── final/
```

## Key dependencies

- `google-genai>=1.0.0` — unified Google GenAI SDK (Imagen + Veo)
- `Pillow>=10.0.0` — image handling
- `python-dotenv>=1.0.0` — .env file loading
- `pyyaml>=6.0` — project.yaml parsing
- `pytest` — testing
- `ruff` — linting and formatting
- `ffmpeg` — system dependency for Ken Burns and assembly

## API usage notes

- Imagen generates stills via `client.models.generate_images()`
- Veo generates video via `client.models.generate_videos()` — long-running operation, must be polled
- Veo output goes to a GCS bucket (required by Vertex AI) — configured in `.env`
- For Vertex AI: set `USE_VERTEX=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`
- For Gemini Developer API: set `GEMINI_API_KEY`
- Reference images can be uploaded alongside prompts for style consistency
- Scene 1 should be generated first and used as style reference for subsequent scenes

## Environment variables (.env in project directory)

```
# Vertex AI backend
USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_OUTPUT_BUCKET=gs://your-bucket-name/

# OR Gemini Developer API backend
# GEMINI_API_KEY=your-api-key
```

## Models

- Imagen: `imagen-4.0-generate-001`
- Veo: `veo-3.1-fast-generate-001`

## project.yaml schema

```yaml
title: "Project Title"
aspect_ratio: "9:16"  # 9:16, 16:9, 4:3, 1:1

style_prefix: >
  Detailed visual style description applied to all scene prompts.
  Be specific: art style, colour palette, lighting, setting details.
  This is prepended to every scene prompt for consistency.

characters:
  boy:
    description: >
      Physical description for prompt consistency. Include clothing,
      hair, distinguishing features. Be detailed enough that the AI
      renders the same character across scenes.
    reference: "references/boy.jpg"    # optional path to reference image

  mum:
    description: >
      Another character description. Reference can be null if no
      reference image is available.
    reference: null

scenes:
  # Comments can organise scenes into stanzas/acts/sections
  # === ACT 1 ===

  - number: 1
    title: "Opening shot"
    camera: "WIDE"         # WIDE, CLOSE, WINDOW, or custom string
    type: still             # still (Imagen) or clip (Veo)
    duration: 8             # seconds — match to voice-over timing
    ken_burns: "zoom_in"    # zoom_in, zoom_out, pan_ltr, pan_rtl, static, null
    characters: [boy, mum]  # optional — character IDs for reference images
    prompt: >
      Detailed scene description for the AI model. Include character
      positions, expressions, actions, background details, lighting,
      mood. The more specific, the better the output.

  - number: 2
    title: "Action sequence"
    camera: "CLOSE"
    type: clip              # Veo generates video — use for motion
    duration: 7
    characters: [boy]
    prompt: >
      Clips don't use ken_burns (it's for stills only). Describe
      the motion/action you want in the video.
```

### Schema notes

- `duration` should match voice-over timing (stanza breaks)
- `camera` is advisory — it's included in prompts for the AI, not enforced
- `ken_burns` only applies to stills; clips are already video
- `characters` links to character definitions for reference image lookup
- Scene 1 should be generated first and used as style reference for subsequent scenes

## TDD approach

Tests first. The generate module should be testable with mocked API responses (external HTTP API — acceptable per TESTING.md). Config and models should be tested with real YAML fixtures.

## Makefile targets

- `make install` — create venv, install deps
- `make test` — run all tests
- `make lint` — ruff check + format check
- `make lint-fix` — auto-fix
- `make clean` — remove build artefacts
- `make release [VERSION=x.y.z]` — full release: test, tag, GitHub release, Homebrew update
- `make formula` — update Homebrew formula SHA256 for current version
- `make brew-upgrade` — upgrade local Homebrew install
- `make sync` — git add/commit/pull/push
