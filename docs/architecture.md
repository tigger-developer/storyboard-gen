<!-- Version: 1.2 | Last updated: 2026-02-18 -->

# Architecture: storyboard-gen

## Overview

storyboard-gen is a Python CLI tool. It reads a `project.yaml` from the current working directory, calls AI image/video APIs to generate stills and clips, and optionally assembles them into a final video with Ken Burns effects.

## Components

### CLI layer (`cli.py`, `__main__.py`)

Parses command-line arguments and dispatches to the appropriate module. Subcommands: `generate`, `assemble`, `kdenlive`, `validate`, `list`.

### Configuration layer (`config.py`)

Loads `project.yaml` from the current directory. Loads `.env` for API credentials. Validates the schema, resolves reference image paths, and parses provider configuration.

### Models (`models.py`)

Pure dataclasses: `Project`, `Scene`, `Character`, `ProviderConfig`. No behaviour, just structured data parsed from the YAML.

### Provider layer (`providers/`)

Pluggable image/video generation backends. Each provider implements the `ImageProvider` ABC:

- `providers/base.py` — Abstract base class defining `generate_still()` and `generate_clip()` interface.
- `providers/google.py` — Google Vertex AI / Gemini (Imagen for stills, Veo for clips).
- `providers/fal.py` — FAL.ai (Flux 1.x, Flux 2, and Kontext models for stills, Kling models for clips). Kontext models auto-route to image-to-image (when a reference image exists) or text-to-image (when no reference). Flux 2 models (`_is_flux2` detection) do not support reference images. Kling O3 models support character elements for multi-character consistency. Safety defaults are injected per model family before user options merge.
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

Concatenates all scene outputs (Ken Burns stills + video clips) in order using FFmpeg. When an audio path is provided, runs a two-pass process: concat to temp file, then mux audio with `-shortest` to match the shorter of video/audio. Cleans up temp files in a `try`/`finally` block.

### Kdenlive export (`kdenlive.py`)

Generates a Kdenlive project file (MLT XML format) for timeline editing. References still PNGs directly (not pre-rendered intermediate MP4s), with Ken Burns pan/zoom effects applied via Kdenlive's native `qtblend` transform filter. Audio producers are tagged with `video_index=-1`, `audio_index=0`, and `kdenlive:clip_type=1` so MLT handles them as audio-only clips. When ffprobe is available, audio metadata (sample rate, channels, codec) is probed at export time. The output `.kdenlive` file can be opened in Kdenlive for fine-tuning timing, adjusting Ken Burns keyframes, and adding transitions before final render.

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
              ──▶ (optional) audio mux via FFmpeg
    │
    ▼
kdenlive.py ──▶ output/final/{title}.kdenlive
              ──▶ MLT XML with stills (qtblend Ken Burns), clips, audio
```

## Audio resolution

The `assemble` command resolves audio via this priority chain:

1. `--preview` flag → no audio (regardless of other settings)
2. CLI `--audio <path>` → explicit override
3. `project.yaml` `audio:` field → project default
4. None → assemble without audio

If the resolved path doesn't exist, a warning is logged and assembly proceeds without audio.

## Reference image resolution

`Project.get_reference_images(scene)` is the single chokepoint for reference images. All code paths (generate_still, generate_clip, all providers) consume its output.

1. **Scene-level override**: If `scene.reference` is non-empty, return those paths (filtering to existing files). This replaces character-based lookup entirely for the scene.
2. **Character-level fallback**: Otherwise, flatten all reference lists from characters listed in the scene, filtering to existing files.

Both `Character.reference` and `Scene.reference` are `list[Path]` (empty list when unset). Multiple references per character/scene are supported — e.g. front/side/detail views for better consistency. Veo supports up to 3 asset references; FAL and Replicate use only the first and log a warning.

## Provider selection

1. Per-scene `provider:` override — full control (highest priority)
2. Per-scene `model:` override — model-only shorthand, inherits backend and options from the project-level provider (or Google default). Cannot be combined with `provider:` on the same scene.
3. Project-level `providers.still` / `providers.clip`
4. Default: Google with Imagen 4 (stills) / Veo 3.1 (clips)

## Character elements (O3)

Kling O3 models support character-consistent video generation via an `elements[]` array. storyboard-gen maps `project.yaml` character definitions to O3 elements automatically:

- Users write `@character_id` tokens (e.g. `@boy`, `@mum`) in scene prompts
- For O3 models: `@boy` → `@Element1`, `@mum` → `@Element2` (ordered by scene's `characters` list)
- For non-O3 models: the `@` prefix is stripped (e.g. `@boy` → `boy`)
- When no `@character_id` tokens appear, descriptions are auto-prepended as `@ElementN is <description>`
- Character reference images are uploaded to FAL CDN and mapped to `frontal_image_url` (first ref) and `reference_image_urls` (additional refs)
- CDN URLs are cached in `logs/cdn_cache.json` (SHA-256 hash → URL) to avoid re-uploading across sessions

## External dependencies

- Google Vertex AI / Gemini API (optional — `pip install storyboard-gen[google]`)
- FAL.ai API (optional — `pip install storyboard-gen[fal]`)
- Replicate API (optional — `pip install storyboard-gen[replicate]`)
- FFmpeg (system binary, must be on PATH)
- Python 3.12+

## Configuration precedence

1. Command-line arguments
2. Per-scene `provider:` override in `project.yaml`
3. Per-scene `model:` override in `project.yaml` (inherits backend/options)
4. Project-level provider config in `project.yaml`
5. `.env` in project directory
6. Environment variables
7. Defaults in code
