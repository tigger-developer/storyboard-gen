<!-- Version: 0.1 | Last updated: 2026-02-12 -->

# Architecture: storyboard-gen

## Overview

storyboard-gen is a Python CLI tool. It reads a `project.yaml` from the current working directory, calls Google GenAI APIs to generate images and video clips, and optionally assembles them into a final video with Ken Burns effects.

## Components

### CLI layer (`cli.py`, `__main__.py`)

Parses command-line arguments and dispatches to the appropriate module. Subcommands: `generate`, `assemble`, `validate`, `list`.

### Configuration layer (`config.py`)

Loads `project.yaml` from the current directory. Loads `.env` for API credentials. Validates the schema and resolves reference image paths.

### Models (`models.py`)

Pure dataclasses: `Project`, `Scene`, `Character`. No behaviour, just structured data parsed from the YAML.

### Client (`client.py`)

Creates a `google.genai.Client` configured for either Vertex AI or Gemini Developer API, based on environment variables.

### Generation (`generate.py`)

Two main functions:
- `generate_still(scene, project)` — calls Imagen, returns image bytes, saves to `output/stills/`
- `generate_clip(scene, project)` — calls Veo (long-running op), polls for completion, downloads from GCS, saves to `output/clips/`

Both prepend the project's `style_prefix` to the scene prompt and include character reference images where specified.

### Ken Burns (`ken_burns.py`)

Applies zoom/pan effects to still images using FFmpeg, producing short video clips at the scene's specified duration.

### Assembly (`assemble.py`)

Concatenates all scene outputs (Ken Burns stills + video clips) in order using FFmpeg. Optionally adds crossfade transitions.

## Data flow

```
project.yaml
    │
    ▼
config.py ──▶ models.py (Project, Scene, Character)
    │
    ▼
client.py ──▶ google.genai.Client
    │
    ▼
generate.py ──▶ output/stills/*.png
            ──▶ output/clips/*.mp4
    │
    ▼
ken_burns.py ──▶ output/intermediate/*.mp4 (stills with effects)
    │
    ▼
assemble.py ──▶ output/final/assembled.mp4
```

## External dependencies

- Google Vertex AI / Gemini API (network)
- Google Cloud Storage bucket (for Veo output)
- FFmpeg (system binary, must be on PATH)
- Python 3.12+

## Configuration precedence

1. Command-line arguments
2. `.env` in project directory
3. Environment variables
4. Defaults in code
