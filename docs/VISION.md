<!-- Version: 0.5 | Last updated: 2026-08-27 -->

# Vision: storyboard-gen

## Purpose

A CLI tool (with optional GUI) that turns a YAML storyboard into a sequence of AI-generated images and video clips, ready for assembly in a video editor.

## Problem

Generating a short video from a storyboard using AI image/video APIs involves repetitive boilerplate: API client setup, prompt engineering with style prefixes, polling for long-running operations, downloading results, applying Ken Burns effects. Each new project repeats this work.

## Solution

Separate the creative decisions (storyboard, prompts, character designs, style) from the plumbing (API calls, file handling, effects). The creative work lives in a simple `project.yaml` file. The plumbing is a reusable CLI tool.

## Workflow

1. Creative planning (in conversation, sketches, notes) produces a `project.yaml`
2. Reference images go in `references/`
3. `storyboard-gen generate` calls the APIs and saves results to `output/`
4. `storyboard-gen assemble` applies Ken Burns effects and concatenates a quick-preview video
5. `storyboard-gen kdenlive` exports a complete Kdenlive project for professional editing
6. `storyboard-gen fcpxml` exports a Final Cut Pro project for professional editing

The optional GUI (`storyboard-gen-gui`) provides visual scene management for steps 3–4 without replacing the CLI.

## Editor project exports

The `kdenlive` command produces a Kdenlive project file and `fcpxml` produces a Final Cut Pro project file. Each export places scenes at their configured durations, applies native Ken Burns effects, and includes configured audio and subtitles. The exported project opens in its target editor for timing, keyframe, title, transition, and render work.

---

## Changelog

- **0.5** (2026-08-27): Added Final Cut Pro export to the documented workflow.

## Non-goals

- This is not a full video editor
- This does not handle audio editing (mixing, effects, trimming) — it can overlay a pre-prepared audio track during assembly
- This does not upload to social media
- This does not manage cloud billing or quotas

## Audio support

The `assemble` command can mux a single audio file (voice-over, soundtrack) into the final video. Audio is configured via the `audio:` field in `project.yaml` or the `--audio` CLI flag. The `--preview` flag skips audio. Full audio editing (mixing, trimming, effects) remains out of scope — prepare audio externally.

## Supported providers

storyboard-gen has a pluggable provider system. Multiple providers can be used within the same project — configure a default in `project.yaml` and override per scene.

- **Google** — Imagen (stills), Veo (clips). Auth via Vertex AI (GCP) or Gemini API key. Default provider.
- **FAL.ai** — Flux, Kontext, Kling (stills and clips). Multi-character support via `@character_id` mapping. Auth via `FAL_KEY`.
- **Replicate** — Flux models (stills only). Auth via `REPLICATE_API_TOKEN`.

See [models.md](models.md) for the full model reference, including capabilities, options, and a choosing guide.
