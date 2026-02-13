<!-- Version: 0.3 | Last updated: 2026-02-13 -->

# Architecture: storyboard-gen

## Overview

storyboard-gen is a Python CLI tool. It reads a `project.yaml` from the current working directory, calls AI image/video APIs to generate stills and clips, and optionally assembles them into a final video with Ken Burns effects.

## Components

### CLI layer (`cli.py`, `__main__.py`)

Parses command-line arguments and dispatches to the appropriate module. Subcommands: `generate`, `assemble`, `validate`, `list`.

### Configuration layer (`config.py`)

Loads `project.yaml` from the current directory. Loads `.env` for API credentials. Validates the schema, resolves reference image paths, and parses provider configuration.

### Models (`models.py`)

Pure dataclasses: `Project`, `Scene`, `Character`, `ProviderConfig`. No behaviour, just structured data parsed from the YAML.

### Provider layer (`providers/`)

Pluggable image/video generation backends. Each provider implements the `ImageProvider` ABC:

- `providers/base.py` — Abstract base class defining `generate_still()` and `generate_clip()` interface.
- `providers/google.py` — Google Vertex AI / Gemini (Imagen for stills, Veo for clips).
- `providers/fal.py` — FAL.ai (Flux and Kontext models for stills). Kontext models auto-route to image-to-image (when a reference image exists) or text-to-image (when no reference).
- `providers/replicate.py` — Replicate (Flux models for stills).
- `providers/__init__.py` — Registry and factory. Uses lazy imports so unused SDKs are not required.

Providers are configured in `project.yaml` via the `providers` section, with per-scene overrides possible. Projects without a `providers` section default to Google.

### Generation orchestrator (`generate.py`)

Thin orchestrator that resolves the provider, delegates generation, and handles post-processing:

- `generate_still(scene, project)` — resolves provider, calls `provider.generate_still()`, applies aspect ratio crop, archives previous output, saves PNG.
- `generate_clip(scene, project)` — resolves provider, calls `provider.generate_clip()`, archives previous output, saves MP4.

### Ken Burns (`ken_burns.py`)

Applies zoom/pan effects to still images using FFmpeg, producing short video clips at the scene's specified duration.

### Assembly (`assemble.py`)

Concatenates all scene outputs (Ken Burns stills + video clips) in order using FFmpeg. Optionally adds crossfade transitions.

## Data flow

```
project.yaml
    │
    ▼
config.py ──▶ models.py (Project, Scene, Character, ProviderConfig)
    │
    ▼
generate.py ──▶ providers/ (Google, FAL, Replicate)
            ──▶ output/stills/*.png
            ──▶ output/clips/*.mp4
    │
    ▼
ken_burns.py ──▶ output/intermediate/*.mp4 (stills with effects)
    │
    ▼
assemble.py ──▶ output/final/assembled.mp4
```

## Provider selection

1. Per-scene `provider:` override (highest priority)
2. Project-level `providers.still` / `providers.clip`
3. Default: Google with Imagen 4 (stills) / Veo 3.1 (clips)

## External dependencies

- Google Vertex AI / Gemini API (optional — `pip install storyboard-gen[google]`)
- FAL.ai API (optional — `pip install storyboard-gen[fal]`)
- Replicate API (optional — `pip install storyboard-gen[replicate]`)
- FFmpeg (system binary, must be on PATH)
- Python 3.12+

## Configuration precedence

1. Command-line arguments
2. Per-scene provider override in `project.yaml`
3. Project-level provider config in `project.yaml`
4. `.env` in project directory
5. Environment variables
6. Defaults in code
