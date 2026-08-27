<!-- Version: 2.14 | Last updated: 2026-08-27 -->

# Architecture: storyboard-gen

## Overview

storyboard-gen is a Python CLI tool with an optional GUI. It reads a `project.yaml` from the current working directory, calls AI image/video APIs to generate stills and clips, and optionally assembles them into a final video with Ken Burns effects. The GUI provides visual scene management and generation controls via PySide6, complementing (not replacing) the CLI.

## Components

### CLI layer (`cli.py`, `__main__.py`)

Parses command-line arguments and dispatches to the appropriate module. Subcommands: `generate`, `assemble`, `kdenlive`, `fcpxml`, `validate`, `list`, `init`, and `schema`. Argparse setup is decomposed into per-subcommand helpers (`_add_generate_parser()`, `_add_assemble_parser()`, and export helpers) coordinated by `_build_parser()`. The top-level help epilog is loaded from `docs/storyboard-gen-help.md`; it points checkout users to the local `README.md` and installed users to the canonical GitHub repository URL. The `init` subcommand scaffolds new projects using template files loaded via `importlib.resources` from the `templates/` package.

### Configuration layer (`config.py`)

Loads `project.yaml` from the current directory. Loads `.env` for API credentials. Validates the schema, resolves reference image paths, and parses provider configuration.

### Models (`models.py`)

Dataclasses `Project`, `Scene`, `Character`, and `ProviderConfig` represent validated YAML. `Project` also provides prompt construction, reference-image resolution, scene lookup, and the normalized export filename stem.

### Provider layer (`providers/`)

Pluggable image/video generation backends. Each provider implements the `ImageProvider` ABC:

- `providers/base.py` — Abstract base class defining `generate_still()` and `generate_clip()` interface.
- `providers/google.py` — Google Vertex AI / Gemini (Imagen for stills, Veo for clips). Clip generation is decomposed into `_build_clip_config()`, `_build_clip_references()`, `_poll_operation()`, and `_extract_clip_results()`.
- `providers/fal.py` — FAL.ai (Flux, Kontext, O1 Image, Grok, Seedream, Hunyuan Image, Recraft, FireRed, Qwen Image, GLM Image, Nano Banana, Emu, GPT Image, and Reve still models; Kling, Grok Video, Seedance, Hunyuan Video, Wan, and MiniMax clip models). A `StillHandler` strategy registry selects specialized model-family argument builders. Generic `EditHandler` routing uses the explicit `EDIT_SIBLINGS` mapping in `model_registry.py`; it does not derive endpoints by suffix stripping. The text-to-image endpoint is always the configured model ID and models with references route to their registered edit sibling where available. Specialized handlers support model-specific reference and `@character_id` behaviour. Clip generation uses model-specific argument building and t2v/i2v auto-routing where the model family supports it. Safety defaults are applied before user options. Reference uploads are fresh for each generation because FAL CDN URL retention is not guaranteed.
- `providers/replicate.py` — Replicate (Flux models for stills).
- `providers/__init__.py` — Registry and factory. Uses lazy imports so unused SDKs are not required.

Providers are configured in `project.yaml` via the `providers` section, with per-scene overrides possible. Projects without a `providers` section default to Google.

### Error formatting (`errors.py`)

`clean_api_error(raw)` extracts human-readable messages from raw API error objects (dicts, lists, strings). Used by all providers to present clean error messages in both CLI and GUI.

### Model registry (`model_registry.py`)

Centralized registry of known backends and their common models (`BACKEND_MODELS`). Used by the GUI project settings form for cascading backend→model dropdowns. Users can type custom model IDs.

### Generation orchestrator (`generate.py`)

Thin orchestrator that resolves the provider, delegates generation, and handles post-processing:

- `generate_still(scene, project)` — resolves provider, calls `provider.generate_still()`, applies aspect ratio crop, archives previous output, saves PNG.
- `generate_clip(scene, project)` — resolves provider, calls `provider.generate_clip()`, archives previous output, saves MP4.

### Pricing (`pricing.py`)

Unified pricing lookup with priority chain: **project.yaml override > FAL live API > static defaults (Google, Replicate) > None**. Provides cost estimates for `--dry-run` and GUI display. Cost estimates are indicative — FAL prices are live; Google and Replicate use static defaults that may be outdated.

- `fetch_price(model, pricing_override=None)` — resolves pricing using the priority chain. FAL models use `GET https://api.fal.ai/v1/models/pricing?endpoint_id=<model>` with `FAL_KEY` (session-cached). Google models (Imagen, Veo) and Replicate models (Flux Pro, Flux Dev) use built-in `_STATIC_PRICES` defaults. Project-level `pricing` overrides in `project.yaml` take highest priority.
- `_STATIC_PRICES` — dict of hardcoded pricing for Google models (Imagen 4 Fast/Standard/Ultra, Veo 2/3/3.1) and Replicate models (Flux Pro 1.1, Flux Dev).
- `estimate_scene_cost(scene, pricing)` — calculates per-scene cost: flat `unit_price` for stills (per-image), `unit_price * ~1MP` for megapixel-priced models (standard Flux output), `unit_price * duration` for clips.
- `format_cost_line(scene, pricing)` — human-readable cost string for CLI dry-run output.

### SRT parser (`srt.py`)

Parses `.srt` subtitle files into `Subtitle` dataclasses (index, start/end milliseconds, text).

### Subtitle module (`subtitles.py`)

Multi-format subtitle parser and ASS writer. Supports SRT, WebVTT, ASS/SSA input formats. `parse_subtitle_file(path)` auto-detects format by extension. `to_ass(subtitles, width, height)` generates Kdenlive-compatible ASS output with `[Script Info]`, `[Kdenlive Extradata]`, `[V4+ Styles]`, and `[Events]` sections.

### Ken Burns (`ken_burns.py`)

Applies zoom/pan effects to still images using FFmpeg, producing short video clips at the scene's specified duration.

### Assembly (`assemble.py`)

Concatenates all scene outputs (Ken Burns stills + video clips) in order using FFmpeg. When an audio path is provided, runs a two-pass process: concat to temp file, then mux audio with `-shortest` to match the shorter of video/audio. Cleans up temp files in a `try`/`finally` block.

### Kdenlive export (`kdenlive.py`)

Generates a Kdenlive project file (MLT XML format) for timeline editing. References still PNGs directly (not pre-rendered intermediate MP4s), with Ken Burns pan/zoom effects applied via Kdenlive's native `qtblend` transform filter at the timeline level (playlist `<entry>`, not `<producer>`) so the project bin clip stays clean for reuse. Audio producers are tagged with `video_index=-1`, `audio_index=0`, and `kdenlive:clip_type=1` so MLT handles them as audio-only clips. Still image producers have `eof=pause`, `mlt_service=qimage`, and `kdenlive:clip_type=2`; clip producers have `eof=pause`. When ffprobe is available, audio metadata (sample rate, channels, codec) is probed at export time. Internal transitions carry `kdenlive_id` properties (`mix`/`qtblend`) and qtblend transitions include `compositing=0`, `distort=0`, `rotate_center=0` to match native Kdenlive defaults. Ken Burns transform filters include `rotate_center=0`, `compositing=0`, and `distort=0`. Video/audio track tractors carry `kdenlive:track_name` metadata. The sequence tractor includes disabled `volume` and `panner` filters (`internal_added=237`, `disable=1`) expected by Kdenlive's audio mixing UI. Subtitle support uses Kdenlive's native subtitle track: input files (SRT, VTT, ASS/SSA) are converted to ASS format via `subtitles.py` and written alongside the `.kdenlive` project as `{project}.kdenlive.ass`. The subtitle `av.filename` and `subtitlesList` JSON use relative filenames (not absolute paths) for project portability. The sequence tractor gets an `avfilter.subtitles` filter with `internal_added=237` and `av.alpha=1`, plus `subtitlesList` JSON and `hidesubtitle=0` metadata properties. Both CLI and GUI pass `subtitles_path` from `project.subtitles` (skipped in preview mode, with existence check). The output `.kdenlive` file can be opened in Kdenlive for fine-tuning timing, adjusting Ken Burns keyframes, and adding transitions before final render.

### Final Cut Pro export (`fcpxml.py`)

Generates an FCPXML 1.14 project for Final Cut Pro 12. Stills and clips are placed in a primary storyline in YAML order. Still-image Ken Burns effects use native `adjust-crop` pan rectangles. Optional audio is placed on lane `-1`, and SRT, VTT, ASS, or SSA subtitles are represented as Basic Title elements on lane `1`. The CLI and GUI use the same snake_case filename stem for default Kdenlive and FCPXML export names.

### GUI layer (`gui/`) — optional

A PySide6 (Qt6) graphical interface that wraps the operational commands. Installed via `pip install storyboard-gen[gui]`. The GUI supports limited editing of `project.yaml` via a settings form (title, providers, aspect ratio, style prefix, audio/subtitles, character descriptions).

- `gui/app.py` — `MainWindow` with icon-only toolbar (Open Project, New Project, Refresh, Generate, Stop, Output, View YAML, Edit YAML, Console, About), splitter layout, progress label, and signal wiring. Toolbar buttons are `QToolButton` widgets with emoji icons, tooltips, and platform-aware keyboard shortcut hints (Cmd on macOS, Ctrl on Linux/Windows). Keyboard shortcuts: Cmd/Ctrl+O (Open), N (New), R (Refresh), G (Generate), S (Save YAML), Y (View YAML), L (Console), I (About); Cmd/Ctrl+Shift+C (Stop), Shift+O (Output), Shift+Y (Edit YAML); Cmd/Ctrl+[ and ] for scene navigation. New Project prompts for a location and name, scaffolds via `init_project()`, and opens the new project. Refresh reloads `project.yaml` from disk. Generation always reloads `project.yaml` and `.env` from disk before creating a worker, ensuring external edits are picked up without requiring a manual Refresh. Generate dialog includes a dry-run checkbox: when checked, prints scene info (provider, model, prompt, cost) to the console without making API calls. Generation errors log to the console instead of showing modal dialogs, allowing concurrent interaction with other scenes. Worker cleanup is deferred to `QThread.finished` to prevent crashes from GC destroying the thread while the OS thread is still running. Output opens an `OutputDialog` for MP4 assembly, Kdenlive export, or Final Cut Pro export. About opens an `AboutDialog` showing version and GitHub link. `_install_excepthook()` logs unhandled exceptions in Qt slots. Entry point: `run()`.
- `gui/about_dialog.py` — `AboutDialog(QDialog)` displaying app name, version, brief description, and clickable GitHub link. Single Close button.
- `gui/scene_list.py` — `SceneListWidget` shows scenes with `SceneItemWidget` custom widgets: status indicator, scene info label, per-scene cost estimate, inline Generate/Regenerate button, and Archive button. Uses `ExtendedSelection` mode for Cmd+click / Shift+click multi-select. `load_project()` accepts an optional `pricing_map` to display per-scene costs. `get_selected_scenes()` returns all selected scenes in order; `get_selected_scene()` returns the current row. `get_scene_status()` checks output file existence. Emits `scene_selected(Scene)`, `generate_requested(Scene)`, and `archive_requested(Scene)`.
- `gui/preview_panel.py` — `PreviewPanel` with `QStackedLayout` switching between placeholder, still image, clip info (thumbnail + file details), and inline video playback views. Video playback uses `QMediaPlayer` + `QVideoWidget` (QtMultimedia) with play/pause controls. Falls back to clip info view on playback error. Extracts thumbnails from video clips via ffmpeg for the fallback view.
- `gui/console_panel.py` — `ConsolePanel` read-only text display. `QtLogHandler` bridges Python `logging` to Qt signals.
- `gui/generate_dialog.py` — `GenerateDialog(QDialog)` with radio buttons: all scenes, all stills, all clips, or selected scene(s). Includes a dry-run checkbox for preview-only mode. Accepts a list of selected scenes for multi-scene generation; shows count or single scene title. Displays estimated cost summary when a `pricing_map` is provided, updating dynamically as the user changes the selection.
- `gui/generate_worker.py` — `GenerateWorker(QThread)` runs generation in the background, emitting progress signals. Supports cooperative stop via `request_stop()`: emits `stopped(Scene)` on completion when stop was requested, enabling proper state cleanup. Emits `scene_started(Scene)`, `scene_finished(Scene)`, `stopped(Scene)`, and `error(str)`.
- `gui/output_dialog.py` — `OutputDialog(QDialog)` with radio group (Assemble MP4 / Kdenlive export / Final Cut Pro export), preview mode checkbox, audio file picker, and output filename field. Preview suppresses configured audio and subtitles. Returns options via `get_options()`.
- `gui/archive_dialog.py` — `ArchiveDialog(QDialog)` for browsing and restoring previously generated scene outputs. Lists archived versions (from `output/{stills,clips}/archive/`) with timestamps, shows preview thumbnails for stills, and supports restore (swap selected archive ↔ current output). Utility functions: `list_scene_archives()`, `restore_archive()`, `get_scene_archive_dir()`, `get_scene_output_path()`, `parse_archive_timestamp()`.
- `gui/yaml_viewer.py` — `YamlViewer` with `YamlHighlighter(QSyntaxHighlighter)` for syntax colouring. Contains a horizontal splitter: `ProjectSettingsForm` (editable fields) on the left, read-only YAML display on the right. `load_project()` populates both. Saving the form refreshes the YAML and emits `project_saved`.
- `gui/project_settings.py` — `ProjectSettingsForm(QWidget)` for editing project-level YAML fields: title, aspect ratio, style prefix, still/clip provider backends and models (cascading dropdowns), audio/subtitles file pickers, and per-character descriptions. Uses format-preserving YAML round-trip via `ruamel.yaml`. Emits `saved` when changes are written.
- `gui/yaml_editor_helpers.py` — Format-preserving YAML read/write helpers using `ruamel.yaml`. `load_yaml_roundtrip()`, `save_yaml_roundtrip()`, `update_nested()`, `get_nested()`.
- `gui/__main__.py` — `python -m storyboard_gen.gui` and `storyboard-gen-gui` entry point.

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
kdenlive.py ──▶ output/final/{snake_case_title}.kdenlive
              ──▶ MLT XML with stills (qtblend Ken Burns), clips, audio
fcpxml.py   ──▶ output/final/{snake_case_title}.fcpxml
              ──▶ FCPXML with stills, clips, Ken Burns, audio, subtitles
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

Both `Character.reference` and `Scene.reference` are `list[Path]` (empty list when unset). Multiple references per character or scene are supported. Each model family determines whether it accepts one or multiple references; multi-reference FAL models upload all supported images.

## Provider selection

1. Per-scene `provider:` override — full control (highest priority)
2. Per-scene `model:` override — model-only shorthand, inherits backend and options from the project-level provider (or Google default). Cannot be combined with `provider:` on the same scene.
3. Project-level `providers.still` / `providers.clip`
4. Default: Google with Imagen 4 (stills) / Veo 3.1 (clips)

## Character elements and `@character_id` mapping

Multiple FAL models support character-consistent generation via `@character_id` prompt tokens and multi-reference uploads. storyboard-gen maps `project.yaml` character definitions automatically:

- Users write `@character_id` tokens (e.g. `@boy`, `@mum`) in scene prompts
- **O3 clips:** `@boy` → `@Element1` (character `elements[]` array)
- **O1 Image stills:** `@boy` → `@Image1` (multi-ref `image_urls` + `elements[]`)
- **Flux 2 Pro/Max stills:** `@boy` → `@image1` (edit-endpoint `image_urls`)
- **Kontext Multi stills:** `@` prefix stripped; model infers associations from context
- **All other models:** `@` prefix stripped (e.g. `@boy` → `boy`)
- When no `@character_id` tokens appear, O3, O1, and Flux 2 Pro/Max auto-prepend model-specific tag descriptions
- O3 character elements map the first reference to `frontal_image_url` and additional references to `reference_image_urls`
- Multi-reference handlers upload fresh FAL CDN URLs for each generation

## External dependencies

- Google Vertex AI / Gemini API (optional — `pip install storyboard-gen[google]`)
- FAL.ai API (optional — `pip install storyboard-gen[fal]`)
- Replicate API (optional — `pip install storyboard-gen[replicate]`)
- PySide6 (optional — `pip install storyboard-gen[gui]`)
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

## See also

- [VISION.md](VISION.md) — project goals and non-goals
- [models.md](models.md) — full model reference with capabilities, options, and safety defaults
- [project-yaml-spec.md](project-yaml-spec.md) — complete `project.yaml` schema

---

## Changelog

- **2.14** (2026-08-27): Documented FCPXML export, current filename normalization, explicit FAL edit routing, and current reference-upload behaviour.
