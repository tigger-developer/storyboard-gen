<!-- Version: 1.8 | Last updated: 2026-02-18 -->

# project.yaml Specification

This is the complete schema reference for `project.yaml`, the storyboard definition file used by [storyboard-gen](https://github.com/tigger04/storyboard-gen).

## File location

`project.yaml` must be in the root of your project directory. The tool looks for it in the current working directory when you run any command.

```
my-project/
├── project.yaml          # This file
├── .env                  # API credentials (not committed)
├── audio.m4a             # Optional audio track for assembly
├── references/           # Character/style reference images
│   ├── hero.jpg
│   └── villain.png
└── output/               # Generated assets (created by tool)
    ├── stills/
    ├── clips/
    ├── intermediate/
    └── final/
```

---

## Top-level fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `title` | string | **yes** | — | Project title |
| `aspect_ratio` | string | no | `"16:9"` | Output aspect ratio |
| `audio` | string | no | `null` | Path to audio file for assembly (relative to project dir) |
| `style_prefix` | string | no | `""` | Visual style description prepended to every scene prompt |
| `providers` | object | no | — | AI provider configuration (defaults to Google) |
| `characters` | object | no | `{}` | Named characters with descriptions and reference images |
| `scenes` | list | **yes** | — | At least one scene required |

### `aspect_ratio`

Valid values: `"9:16"`, `"16:9"`, `"4:3"`, `"1:1"`

### `audio`

Optional path to an audio file (voice-over, soundtrack) to mux into the assembled video. Relative to the project directory. The CLI `--audio` flag overrides this value; `--preview` skips audio entirely. If the file doesn't exist at assembly time, a warning is logged and assembly proceeds without audio.

```yaml
audio: "audio.m4a"
```

### `style_prefix`

A detailed visual style description that gets prepended to every scene's prompt. Be specific about art style, colour palette, lighting, setting details. This is what keeps your scenes visually consistent.

---

## `providers` section

Optional. If omitted, defaults to Google (Imagen for stills, Veo for clips).

```yaml
providers:
  still:
    backend: fal
    model: "fal-ai/flux-general"
    options:
      safety_tolerance: 5
  clip:
    backend: google
    model: "veo-3.1-fast-generate-001"
    options: {}
```

### Provider config fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `backend` | string | **yes** | `"google"`, `"fal"`, or `"replicate"` |
| `model` | string | **yes** | Provider-specific model identifier |
| `options` | object | no | Provider-specific options passed through to the API |

### Available backends and models

#### Google (`backend: google`)

| Model | Type | Description |
|-------|------|-------------|
| `imagen-4.0-generate-001` | still | Imagen 4 — default for stills |
| `imagen-3.0-capability-001` | still | Imagen 3 Capability — used automatically for single-reference edits |
| `veo-3.1-fast-generate-001` | clip | Veo 3.1 Fast — default for clips |

**Auth:** Two mutually exclusive paths — when `USE_VERTEX=true` is set, `GEMINI_API_KEY` is ignored. See [docs/models.md](models.md#authentication) for full details including how to switch Google accounts.

#### FAL.ai (`backend: fal`)

| Model | Type | Description |
|-------|------|-------------|
| `fal-ai/flux-general` | still | Flux with reference image support, LoRAs, ControlNets |
| `fal-ai/flux-pro/v1.1` | still | Flux Pro 1.1 — high quality text-to-image |
| `fal-ai/flux-2` | still | Flux 2 — no reference image support |
| `fal-ai/flux-2/turbo` | still | Flux 2 Turbo — fast, no reference image support |
| `fal-ai/flux-pro/kontext` | still | Kontext — image-to-image (with ref) or text-to-image (without) |
| `fal-ai/kling-video/v2.1/pro/text-to-video` | clip | Kling v2.1 Pro — text-to-video |
| `fal-ai/kling-video/v2.1/pro/image-to-video` | clip | Kling v2.1 Pro — image-to-video (with source_frame) |
| `fal-ai/kling-video/v3/standard/image-to-video` | clip | Kling v3 Standard — image-to-video |
| `fal-ai/kling-video/o3/standard/image-to-video` | clip | Kling O3 Standard — supports character elements |

**Still options (Flux 1.x):** `seed` (int), `safety_tolerance` (1-6), `num_inference_steps` (1-50), `guidance_scale` (0-20), `reference_strength` (float).

**Still options (Flux 2):** `seed` (int), `enable_safety_checker` (bool), `guidance_scale` (float), `acceleration` (string), `enable_prompt_expansion` (bool). No reference image support.

Safety defaults are injected automatically (see [docs/models.md](models.md) for details).

**Clip options:** `cfg_scale` (float), `negative_prompt` (string), `generate_audio` (bool, default false).

Kling clip endpoints auto-route: `text-to-video` ↔ `image-to-video` based on whether `source_frame` is set.

Requires `FAL_KEY` in `.env`.

#### Replicate (`backend: replicate`)

| Model | Type | Description |
|-------|------|-------------|
| `black-forest-labs/flux-1.1-pro` | still | Flux Pro 1.1 — text-to-image only |
| `black-forest-labs/flux-dev` | still | Flux Dev — supports image-to-image with references |

**Options:** `seed` (int), `safety_tolerance` (0-6), `output_quality` (0-100), `prompt_upsampling` (bool).

Stills only — does not support clips. Requires `REPLICATE_API_TOKEN` in `.env`.

### Provider selection priority

1. Per-scene `provider:` override (highest)
2. Project-level `providers.still` / `providers.clip`
3. Default: Google with `imagen-4.0-generate-001` (stills) / `veo-3.1-fast-generate-001` (clips)

---

## `characters` section

Optional. Maps character IDs to descriptions and reference images.

```yaml
characters:
  hero:
    description: >
      A 10-year-old boy with messy red hair, freckles, green eyes.
      Wearing a blue hoodie and worn jeans. Energetic expression.
    reference:
      - "references/hero_front.jpg"
      - "references/hero_side.jpg"

  villain:
    description: >
      Tall woman in a dark cloak, silver hair, piercing grey eyes.
      Angular features, commanding presence.
    reference: []
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | no | Physical description included in prompts for consistency |
| `reference` | list | no | List of reference image paths, relative to project directory |

### Notes

- Character IDs are used in scene `characters` lists.
- Reference images are uploaded to the provider for style-consistent generation.
- Multiple reference images per character are supported (e.g. front/side/detail views). Veo supports up to 3 asset references.
- FAL and Replicate providers use only the first reference image and log a warning when multiple are provided.
- The reference paths are resolved relative to the project directory.
- Missing reference files are silently skipped at generation time (not at validation).
- **Breaking change (v0.29.0):** `reference` must be a list. A bare string value produces a `ConfigError` with migration instructions.

### `@character_id` in prompts

You can reference characters in scene prompts using `@character_id` (e.g. `@hero`, `@guide`). The behaviour depends on the provider:

- **Kling O3 models:** `@hero` → `@Element1`, `@guide` → `@Element2` (mapped to O3's character element system). Reference images are uploaded as elements for multi-character consistency.
- **All other models:** The `@` prefix is stripped (e.g. `@hero` → `hero`). The character name remains in the prompt as natural text.

When a scene lists characters but the prompt contains no `@character_id` tokens, O3 models auto-prepend `@ElementN is <description>.` lines for each character.

```yaml
scenes:
  - number: 3
    type: clip
    duration: 5
    characters: [hero, guide]
    provider:
      backend: fal
      model: "fal-ai/kling-video/o3/standard/image-to-video"
    prompt: >
      @hero runs toward @guide who is standing at the door.
```

---

## `scenes` section

A list of scenes. At least one scene is required.

```yaml
scenes:
  - number: 1
    title: "Opening shot"
    camera: "WIDE"
    type: still
    duration: 8
    ken_burns: "zoom_in"
    characters: [hero, villain]
    prompt: >
      A wide establishing shot of the hero and villain facing each other
      across a misty bridge at dawn. Golden light breaks through clouds.

  - number: 2
    title: "Chase sequence"
    camera: "CLOSE"
    type: clip
    duration: 7
    characters: [hero]
    provider:
      backend: google
      model: "veo-3.1-fast-generate-001"
    prompt: >
      Dynamic chase through narrow cobblestone streets. The hero sprints,
      looking over his shoulder. Camera follows from behind.
```

### Scene fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `number` | int | no | auto (1-indexed) | Scene number — used for ordering and filenames |
| `title` | string | no | `"Scene N"` | Human-readable scene title |
| `type` | string | no | `"still"` | `"still"` or `"clip"` |
| `prompt` | string | no | `""` | Scene description for the AI model |
| `duration` | number | no | `5` | Duration in seconds (supports decimals, e.g. `2.5`) — match to voice-over timing |
| `camera` | string | no | `null` | Camera angle — injected into AI prompt automatically (see table below) |
| `ken_burns` | string | no | `null` | Ken Burns effect for stills (ignored for clips) |
| `characters` | list | no | `[]` | Character IDs from the `characters` section |
| `provider` | object | no | `null` | Per-scene provider override (same format as `providers.still`) |

### `type`

| Value | Generator | Output |
|-------|-----------|--------|
| `still` | Image model (Imagen, Flux) | `output/stills/scene_NN.png` |
| `clip` | Video model (Veo) | `output/clips/scene_NN.mp4` |

### `ken_burns`

Only applies to stills. Ignored for clips.

| Value | Effect |
|-------|--------|
| `zoom_in` | Slow zoom into the image |
| `zoom_out` | Slow zoom out from the image |
| `pan_ltr` | Pan left to right |
| `pan_rtl` | Pan right to left |
| `static` | No movement |
| `null` (omitted) | No Ken Burns processing |

### `camera`

Standard camera values are automatically injected into the AI prompt as descriptive phrasing. Case-insensitive (e.g. `"wide"` and `"WIDE"` are equivalent). Invalid values are rejected at validation time.

| Value | Injected prompt phrasing |
|-------|--------------------------|
| `EWS` | Extreme wide establishing shot showing the full environment. |
| `WIDE` | Wide shot, full body visible in the environment. |
| `MEDIUM` | Medium shot framed from the waist up. |
| `MCU` | Medium close-up framed from the chest up. |
| `CLOSE` | Close-up of the face, tightly framed. |
| `ECU` | Extreme close-up, tightly cropped to a single detail. |
| `POV` | First-person point of view, seen through the character's eyes. |
| `LOW` | Low angle shot looking upward, character appears dominant. |
| `HIGH` | High angle shot looking downward, character appears small. |
| `OVERHEAD` | Bird's-eye overhead shot looking straight down. |
| `OTS` | Over-the-shoulder shot, shallow depth of field, foreground shoulder blurred. |
| `DUTCH` | Camera tilted 20 degrees off-axis, creating unease. |
| `null` (omitted) | No camera phrasing injected. |

The camera phrasing is inserted between the `style_prefix` and character descriptions in the assembled prompt. Prompt assembly order: **style prefix → camera → characters → scene prompt**.

---

## Complete example

```yaml
title: "The Bridge at Dawn"
aspect_ratio: "9:16"
audio: "narration.m4a"

providers:
  still:
    backend: fal
    model: "fal-ai/flux-general"
    options:
      safety_tolerance: 5
  clip:
    backend: google
    model: "veo-3.1-fast-generate-001"

style_prefix: >
  Cinematic digital illustration in a painterly style with soft warm
  lighting. Muted earth tones with pops of gold and blue. Atmospheric
  depth of field with bokeh highlights. Studio Ghibli-inspired character
  proportions with realistic textures.

characters:
  hero:
    description: >
      A 10-year-old boy with messy auburn hair, round green eyes,
      scattered freckles across his nose. Wears a faded blue hoodie
      two sizes too big, rolled-up sleeves, muddy canvas trainers.
    reference:
      - "references/hero.png"

  guide:
    description: >
      An elderly woman, weathered face, kind brown eyes behind
      round spectacles. White hair in a loose bun. Wears a worn
      green cardigan with patches on the elbows.
    reference: []

scenes:
  # === ACT 1: THE BRIDGE ===

  - number: 1
    title: "Dawn on the bridge"
    camera: "WIDE"
    type: still
    duration: 8
    ken_burns: "zoom_in"
    characters: [hero]
    prompt: >
      Wide establishing shot. The hero stands alone on an ancient
      stone bridge stretching across a misty river valley. Dawn
      light breaks through low clouds, casting long golden shadows.
      The boy looks small against the vast landscape. Morning birds
      circle in the distance.

  - number: 2
    title: "The hero turns"
    camera: "CLOSE"
    type: clip
    duration: 6
    characters: [hero]
    prompt: >
      Close-up of the hero slowly turning to look behind him.
      His expression shifts from wonder to surprise. Wind catches
      his hair. Morning light on his face.

  - number: 3
    title: "The guide appears"
    camera: "MEDIUM"
    type: still
    duration: 5
    ken_burns: "pan_ltr"
    characters: [guide]
    provider:                          # override: use Google for this scene
      backend: google
      model: "imagen-4.0-generate-001"
    prompt: >
      Medium shot. The guide stands at the far end of the bridge,
      silhouetted against the brightening sky. She holds a wooden
      walking stick and a lantern that still glows faintly.
```

---

## Validation

Run `storyboard-gen validate` to check your `project.yaml` for errors before generating. Common issues:

- Missing `title`
- No scenes defined
- Invalid `aspect_ratio` (must be `9:16`, `16:9`, `4:3`, or `1:1`)
- Invalid `type` (must be `still` or `clip`)
- Invalid `ken_burns` value
- Scene references a character ID not defined in `characters`
- Invalid provider `backend` (must be `google`, `fal`, or `replicate`)

## CLI commands

```bash
storyboard-gen validate                     # Validate project.yaml
storyboard-gen list                         # List all scenes with status
storyboard-gen generate --scene 1           # Generate one scene
storyboard-gen generate --scene 1 3 5       # Generate specific scenes in order
storyboard-gen generate --all-stills        # Generate all stills
storyboard-gen generate --all-clips         # Generate all clips
storyboard-gen generate --all              # Generate everything
storyboard-gen assemble                     # Assemble final video (with audio if configured)
storyboard-gen assemble --preview           # Assemble without audio
storyboard-gen assemble --audio voice.m4a   # Override audio track
storyboard-gen kdenlive                     # Export Kdenlive project with Ken Burns effects
storyboard-gen kdenlive --output my.kdenlive # Custom output filename
storyboard-gen --version                    # Show version
```
