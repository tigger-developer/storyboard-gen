# Veo 3.1 Clip Generation Support

## Background

storyboard-gen currently generates video clips via Veo but passes only a
bare prompt — no reference images, no aspect ratio, no image-to-video,
no scene extension. This means clip generation ignores character
references and cannot maintain visual consistency across scenes.

Veo 3.1 supports several features for multi-scene consistency that we
need to expose through the existing provider architecture.

## Requirements

### R1: Pass existing parameters to Veo

`generate_clip` in `providers/google.py` currently ignores `aspect_ratio`
and `reference_images` even though they're passed by the orchestrator.
These must be included in the `GenerateVideosConfig` / `generate_videos`
call.

- `aspect_ratio` → `GenerateVideosConfig(aspect_ratio=...)`
- `reference_images` → `GenerateVideosConfig(reference_images=[...])` as
  `types.Image.from_file()` objects (up to 4)

### R2: Image-to-Video (source_frame)

A scene of type `clip` may specify a `source_frame` path. This is an
existing image (typically a previously generated still) used as the
first frame. Veo animates from this frame.

- New field on `Scene` dataclass: `source_frame: Path | None = None`
- Parsed in `config.py` from `source_frame:` in YAML (path relative to
  project dir)
- Passed to provider as `image=` kwarg on `client.models.generate_videos()`
- Validation: only valid on `type: clip` scenes

### R3: Last Frame Conditioning (last_frame)

A scene may specify both `source_frame` and `last_frame`. Veo
interpolates between the two images.

- New field on `Scene`: `last_frame: Path | None = None`
- Parsed in `config.py` from `last_frame:` in YAML
- Passed via `GenerateVideosConfig(last_frame=...)` as a `types.Image`
- Validation: requires `source_frame` to also be set; only valid on clips

### R4: Scene Extension (extend_from)

A scene may specify `extend_from: <scene_number>`. Veo generates a
continuation from the final second of that scene's previously generated
clip.

- New field on `Scene`: `extend_from: str | None = None`
- Parsed in `config.py` from `extend_from:` in YAML (value is a scene
  number as string)
- The **orchestrator** (`generate.py`) resolves the scene number to an
  actual .mp4 path before calling the provider. Check
  `output/clips/scene_{nn}.mp4` first, then
  `output/intermediate/scene_{nn}.mp4`. Raise `RuntimeError` if not found.
- Passed to provider as `video=` kwarg on `generate_videos()` using
  `types.Video(video_bytes=...)` (read the file bytes)
- Validation: mutually exclusive with `source_frame`; only valid on clips

### R5: Seed for Reproducibility

A scene may specify a `seed` integer.

- New field on `Scene`: `seed: int | None = None`
- Parsed in `config.py` from `seed:` in YAML
- Passed via `GenerateVideosConfig(seed=...)`
- No special validation beyond being an integer

### R6: Multiple Variants

A scene may specify `variants: N` (1–4, default 1) to generate multiple
takes for curation.

- New field on `Scene`: `variants: int = 1`
- Parsed in `config.py` from `variants:` in YAML
- Passed as `GenerateVideosConfig(number_of_videos=N)`
- When variants > 1, save as `scene_01_v0.mp4`, `scene_01_v1.mp4`, etc.
  **Do NOT save a bare `scene_01.mp4`** — the user must review and
  promote their preferred variant (see R6a below).
- When variants = 1 (default), save as the bare `scene_01.mp4` as today.
- Validation: must be 1–4; only meaningful on clips but harmless to
  ignore on stills

### R7: Provider Base Class Update

Update `ImageProvider.generate_clip()` signature in `providers/base.py`
to accept the new keyword arguments:

```
source_frame: Path | None = None
last_frame: Path | None = None
extend_from_video: Path | None = None   # resolved .mp4 path, NOT scene number
seed: int | None = None
number_of_videos: int = 1
```

The FAL and Replicate providers should accept these kwargs but may ignore
them or raise `NotImplementedError` for unsupported features. They must
not break.

### R8: Orchestrator Changes (generate.py)

`generate_clip()` must:

1. Resolve `scene.extend_from` to a file path (see R4 above)
2. Pass all new fields through to the provider
3. Handle the multi-variant return when `variants > 1`

### R9: project.yaml Validation

In `config.py`, add validation for:

- `source_frame` and `extend_from` are mutually exclusive
- `last_frame` requires `source_frame`
- `source_frame`, `last_frame`, `extend_from` only valid on `type: clip`
- `variants` in range 1–4

### R10: CLI — No Changes Required

The existing `storyboard-gen generate --scene N` and `--all-clips`
commands should work without modification. The new features are all
driven by project.yaml fields.

## project.yaml Example (clip scenes)

```yaml
scenes:
  # Image-to-video: animate an existing still
  - number: 1
    title: "Boy on the train"
    type: clip
    duration: 5
    characters: [boy]
    source_frame: "output/stills/scene_01.png"
    prompt: >
      The boy shifts in his seat, kicks one foot idly, glances
      out the window. Subtle movement only.

  # Scene extension: continue from scene 1's clip
  - number: 2
    title: "Counting sheep"
    type: clip
    duration: 5
    characters: [boy]
    extend_from: "1"
    prompt: >
      The boy rolls his eyes upward, lips moving silently. His
      fingers twitch against his knee.

  # Reference images only (no source frame, no extension)
  - number: 3
    title: "Mum's reaction"
    type: clip
    duration: 5
    characters: [mum]
    variants: 2
    seed: 42
    prompt: >
      Close-up of the mother making a shushing gesture.

  # First + last frame interpolation
  - number: 4
    title: "Window opens"
    type: clip
    duration: 5
    source_frame: "output/stills/scene_07.png"
    last_frame: "output/stills/scene_08.png"
    prompt: >
      The woman rises from her seat and reaches for the window.
```

### R6a: Archiving vs Variants — Explicit Rules

There are two distinct file-naming situations. They must not be conflated.

**Archiving (regeneration):** When `generate` is run for a scene that
already has output, the existing file is moved to `archive/` with a
timestamp suffix (e.g. `scene_01_20260215_143000.mp4`). This is the
current behaviour and must be preserved for both stills and clips,
regardless of variant count.

**Variants (multi-take from one generation):** When `variants > 1`, the
API returns multiple outputs from a single call. These are saved with a
`_v{n}` suffix:

```
output/clips/scene_01_v0.mp4
output/clips/scene_01_v1.mp4
```

No bare `scene_01.mp4` is created. The assemble/kdenlive pipeline
expects a bare name per scene, so the user must promote their preferred
variant before assembling.

**Promotion** is currently manual (copy or symlink the chosen variant to
the bare filename). A future `storyboard-gen promote --scene 1
--variant 0` command is out of scope for this work.

**Regeneration of variants:** If the user re-runs generate on a scene
that already has `_v0`, `_v1` files, all existing variant files for that
scene are moved to `archive/` before the new variants are saved. If a
bare `scene_01.mp4` also exists (from a previous promotion or a previous
run with variants=1), it is also archived.

**When variants = 1** (the default), save as the bare `scene_01.mp4`
directly, exactly as today. The `_v{n}` suffix is never used.

## Testing

- Unit tests for new config parsing and validation (valid combos,
  invalid combos, mutual exclusivity)
- Unit test for extend_from path resolution in generate.py (mock
  filesystem)
- Integration test with mocked Google client confirming all new kwargs
  reach `client.models.generate_videos()`
- Existing tests must continue to pass (backward compatibility — scenes
  without the new fields should behave identically)

## Out of Scope

- Audio generation / native Veo audio (we mute clips and overlay our
  own audio in kdenlive)
- Automatic variant selection (user picks manually)
- Changes to the assemble or ken_burns modules
- Changes to FAL or Replicate provider internals
