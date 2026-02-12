<!-- Version: 0.1 | Last updated: 2026-02-12 -->

# Vision: storyboard-gen

## Purpose

A CLI tool that turns a YAML storyboard into a sequence of AI-generated images and video clips, ready for assembly in a video editor.

## Problem

Generating a short video from a storyboard using AI image/video APIs involves repetitive boilerplate: API client setup, prompt engineering with style prefixes, polling for long-running operations, downloading results, applying Ken Burns effects. Each new project repeats this work.

## Solution

Separate the creative decisions (storyboard, prompts, character designs, style) from the plumbing (API calls, file handling, effects). The creative work lives in a simple `project.yaml` file. The plumbing is a reusable CLI tool.

## Workflow

1. Creative planning (in conversation, sketches, notes) produces a `project.yaml`
2. Reference images go in `references/`
3. `storyboard-gen generate` calls the APIs and saves results to `output/`
4. `storyboard-gen assemble` applies Ken Burns effects and concatenates
5. User adds voice-over, music, and final edits in their editor (kdenlive, etc.)

## Non-goals

- This is not a full video editor
- This does not handle audio (voice-over, music)
- This does not upload to social media
- This does not manage Google Cloud billing or quotas

## Supported backends

- Google Vertex AI (Imagen for stills, Veo for clips)
- Google Gemini Developer API (same models, simpler auth)
- Future: other providers could be added behind the same interface
