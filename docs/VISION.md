<!-- Version: 0.4 | Last updated: 2026-02-21 -->

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

The optional GUI (`storyboard-gen-gui`) provides visual scene management for steps 3–4 without replacing the CLI.

## Kdenlive export

The Kdenlive export is what makes storyboard-gen more than a batch image generator. It produces a fully editable timeline project: every scene placed at the correct duration, Ken Burns effects applied as native Kdenlive transforms, audio track included, dissolve transitions between scenes. Open the `.kdenlive` file and you have a working first cut — adjust timing, tweak effects, add titles, swap scenes, or re-render at any resolution. This bridges the gap between AI generation and professional video editing without trying to be a video editor itself.

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
