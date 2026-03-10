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
# Create a new project
storyboard-gen init                     # Scaffold in current directory
storyboard-gen init ~/Movies/my-video   # Scaffold in a named directory

# From within a project directory (e.g. ~/Movies/social/pout/)
storyboard-gen generate --scene 1       # Generate one scene
storyboard-gen generate --scene 1 11    # Generate specific scenes in order
storyboard-gen generate --scene 10-48   # Generate scenes 10 through 48
storyboard-gen generate --scene 1 5 10-15  # Mix individual and range
storyboard-gen generate --all-stills    # Generate all stills
storyboard-gen generate --all-clips     # Generate all video clips
storyboard-gen generate --all           # Generate everything
storyboard-gen assemble                 # Assemble final video (with audio if configured)
storyboard-gen assemble --preview       # Assemble without audio
storyboard-gen assemble --audio vo.m4a  # Override audio track
storyboard-gen kdenlive                 # Export Kdenlive project for editing
storyboard-gen validate                 # Validate project.yaml
storyboard-gen list                     # List all scenes with status

# GUI (requires: pip install .[gui])
storyboard-gen-gui                      # Launch GUI
storyboard-gen-gui ~/Movies/my-video    # Launch GUI with project
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
│       ├── models.py      # Dataclasses: Project, Scene, Character, ProviderConfig
│       ├── generate.py    # Generation orchestrator (delegates to providers)
│       ├── providers/     # Pluggable AI backends
│       │   ├── __init__.py    # Registry and factory
│       │   ├── base.py        # ImageProvider ABC
│       │   ├── google.py      # Google Vertex AI (Imagen + Veo)
│       │   ├── fal.py         # FAL.ai (Flux models)
│       │   └── replicate.py   # Replicate (Flux models)
│       ├── gui/           # Optional PySide6 GUI (pip install .[gui])
│       │   ├── __init__.py
│       │   ├── __main__.py        # python -m storyboard_gen.gui entry
│       │   ├── app.py             # MainWindow, toolbar, signal wiring
│       │   ├── scene_list.py      # Scene list with status indicators
│       │   ├── preview_panel.py   # Still/clip preview (thumbnail + file info)
│       │   ├── console_panel.py   # Log output panel + QtLogHandler
│       │   ├── generate_dialog.py # Generate dialog (all/stills/clips/selected)
│       │   ├── generate_worker.py # QThread background generation with stop
│       │   ├── scene_yaml_editor.py # Editable per-scene YAML with extraction/replacement
│       │   ├── settings.py        # Persistent GUI settings (QSettings wrapper)
│       │   └── yaml_viewer.py     # YAML viewer with syntax highlighting
│       ├── ken_burns.py   # Ken Burns effects via FFmpeg
│       ├── assemble.py    # Final video assembly via FFmpeg
│       └── kdenlive.py    # Kdenlive project export (MLT XML)
└── tests/
    ├── __init__.py
    ├── conftest.py        # Shared fixtures (sample project.yaml, etc.)
    ├── test_config.py
    ├── test_models.py
    ├── test_generate.py
    ├── test_cli.py
    ├── test_gui.py        # GUI widget and integration tests (pytest-qt)
    └── test_kdenlive.py
```

### Per-project structure (created by users)

```
some-project/
├── project.yaml           # Storyboard definition (THE key file)
├── .env                   # API credentials (not committed)
├── audio.m4a              # Optional audio track for assembly
├── references/            # Character/style reference images
│   ├── boy.jpg            # jpg, png, or other image formats
│   └── brow_man.png
└── output/                # Generated assets (created by tool)
    ├── stills/
    ├── clips/
    ├── intermediate/      # Ken Burns output from stills
    └── final/
```

## Key dependencies

Core:
- `Pillow>=10.0.0` — image handling
- `python-dotenv>=1.0.0` — .env file loading
- `pyyaml>=6.0` — project.yaml parsing
- `pytest` — testing
- `ruff` — linting and formatting
- `ffmpeg` — system dependency for Ken Burns and assembly

GUI (optional):
- `PySide6>=6.6.0` — Qt6 graphical interface (`pip install .[gui]`)
- `pytest-qt` — GUI testing

Provider SDKs (optional, install as needed):
- `google-genai>=1.0.0` — Google Vertex AI (Imagen + Veo)
- `fal-client>=0.5.0` — FAL.ai (Flux models)
- `replicate>=1.0.0` — Replicate (Flux models)

## Provider system

Providers are configured in `project.yaml` via the `providers` section. Each provider has a `backend`, `model`, and optional `options`. Individual scenes can override the project-level provider.

Provider resolution order:
1. Per-scene `provider:` override
2. Project-level `providers.still` / `providers.clip`
3. Default: Google with Imagen 4 (stills) / Veo 3.1 (clips)

### Google
- Stills: Imagen via `generate_images()` or `edit_image()` (with references)
- Clips: Veo via `generate_videos()` (long-running operation, polled)
- Auth: `USE_VERTEX=true` + GCP credentials, or `GEMINI_API_KEY`

### FAL.ai
- Stills: Flux and Kontext models via `fal_client.subscribe()`
- Kontext models auto-route: image-to-image (with reference) or text-to-image (without)
- Clips: Not supported (use Google for clips)
- Auth: `FAL_KEY` environment variable
- Reference images uploaded to FAL CDN automatically

### Replicate
- Stills: Flux models via `replicate.run()`
- Clips: Not supported (use Google for clips)
- Auth: `REPLICATE_API_TOKEN` environment variable

## Environment variables (.env in project directory)

```
# Google Vertex AI backend
USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_OUTPUT_BUCKET=gs://your-bucket-name/

# OR Google Gemini Developer API backend
# GEMINI_API_KEY=your-api-key

# FAL.ai backend
# FAL_KEY=your-fal-key

# Replicate backend
# REPLICATE_API_TOKEN=your-replicate-token
```

## Models

- Google Imagen: `imagen-4.0-generate-001`
- Google Veo: `veo-3.1-fast-generate-001`
- FAL Flux: `fal-ai/flux-general`, `fal-ai/flux-pro/v1.1`
- FAL Flux 2: `fal-ai/flux-2`, `fal-ai/flux-2/turbo`, `fal-ai/flux-2/dev` (no reference support)
- FAL Kontext: `fal-ai/flux-pro/kontext` (image-to-image with ref, text-to-image without)
- FAL Kontext Multi: `fal-ai/flux-pro/kontext/max/multi` (multi-ref stills, model infers associations)
- FAL O1 Image: `fal-ai/kling-image/o1` (multi-ref stills with `@ImageN` mapping)
- FAL Ideogram Character: `fal-ai/ideogram/character` (dual-channel: character + style refs)
- Replicate Flux: `black-forest-labs/flux-1.1-pro`, `black-forest-labs/flux-dev`

Safety defaults are injected automatically (overridable via user `options`):
- FAL Flux/Flux 2: `enable_safety_checker: false`
- FAL Kontext/Kontext Multi: `safety_tolerance: "6"`
- Replicate: `safety_tolerance: 6`
- Google, O1 Image, Ideogram Character: no toggle available

## project.yaml schema

```yaml
title: "Project Title"
aspect_ratio: "9:16"  # 9:16, 16:9, 4:3, 1:1
audio: "audio.m4a"    # optional, relative to project dir

# Optional: configure AI providers (defaults to Google if omitted)
providers:
  still:
    backend: fal                # google, fal, or replicate
    model: "fal-ai/flux-general"
    options:                    # passthrough — any model-supported API parameter
      seed: 42
  clip:
    backend: google
    model: "veo-3.1-fast-generate-001"

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
    reference:                         # list of reference image paths
      - "references/boy_front.jpg"
      - "references/boy_side.jpg"

  mum:
    description: >
      Another character description. Omit reference or use empty
      list if no reference images are available.
    reference: []

scenes:
  # Comments can organise scenes into stanzas/acts/sections
  # === ACT 1 ===

  - number: 1
    title: "Opening shot"
    camera: "WIDE"         # EWS, WIDE, MEDIUM, MCU, CLOSE, ECU, POV, LOW, HIGH, OVERHEAD, OTS, DUTCH
    type: still             # still or clip
    duration: 8             # seconds — match to voice-over timing
    ken_burns: "zoom_in"    # zoom_in, zoom_out, pan_ltr, pan_rtl, static, null
    characters: [boy, mum]  # optional — character IDs for reference images
    prompt: >
      Detailed scene description for the AI model. Include character
      positions, expressions, actions, background details, lighting,
      mood. The more specific, the better the output.

  - number: 2
    title: "Kontext portrait"
    camera: "CLOSE"
    type: still
    duration: 6
    model: "fal-ai/flux-pro/kontext"  # model-only override (inherits backend/options)
    characters: [boy]
    prompt: >
      A close-up portrait. Uses Kontext model but inherits the
      project-level FAL backend and options.

  - number: 3
    title: "Action sequence"
    camera: "CLOSE"
    type: clip              # clip generates video — use for motion
    duration: 7
    characters: [boy]
    provider:               # optional full per-scene provider override
      backend: google
      model: "veo-3.1-fast-generate-001"
    prompt: >
      Clips don't use ken_burns (it's for stills only). Describe
      the motion/action you want in the video.

  - number: 4
    title: "Portrait with override"
    camera: "CLOSE"
    type: still
    duration: 5
    characters: [mum]
    reference:                        # overrides character-level references for this scene
      - "references/mum.png"
    prompt: >
      When reference is set on a scene, it replaces the
      character-based reference lookup entirely for that scene.
```

### Schema notes

- `duration` should match voice-over timing (stanza breaks)
- `camera` is automatically injected into the AI prompt as descriptive phrasing (e.g. `WIDE` → "Wide shot, full body visible in the environment."). Must be one of the 12 standard values or null. Validated at config load time
- `ken_burns` only applies to stills; clips are already video
- `characters` links to character definitions for reference image lookup
- `model` on a scene overrides only the model, inheriting backend and options from the project-level provider (or Google default). Cannot be combined with `provider` on the same scene
- `provider` on a scene fully overrides the project-level provider for that scene
- `reference` on a scene overrides the character-level reference image lookup entirely; all providers receive this list instead of character refs. Must be a list (breaking change in v0.29.0)
- Scene 1 should be generated first and used as style reference for subsequent scenes

## TDD approach

Tests first. The generate module should be testable with mocked API responses (external HTTP API — acceptable per TESTING.md). Config and models should be tested with real YAML fixtures.

## Makefile targets

- `make install` — create venv, install deps
- `make install-gui` — install with GUI dependencies (PySide6, pytest-qt)
- `make test` — run all tests
- `make lint` — ruff check + format check
- `make lint-fix` — auto-fix
- `make gui` — launch the GUI
- `make clean` — remove build artefacts
- `make release [VERSION=x.y.z]` — full release: test, tag, GitHub release, Homebrew update
- `make formula` — update Homebrew formula SHA256 for current version
- `make brew-upgrade` — upgrade local Homebrew install
- `make sync` — git add/commit/pull/push
