<!-- Version: 2.0 | Last updated: 2026-03-11 -->

# Model Reference

Comprehensive guide to all AI models supported by storyboard-gen, organised by provider.

**Audio on clips:** All clip providers disable audio generation by default. Google Veo sets `generate_audio=False` in the config; FAL Kling sets `generate_audio: false` in the request. This prevents unwanted AI-generated audio from interfering with your project's audio track.

---

## Google (`backend: google`)

Google models are accessed via Vertex AI (with GCP credentials) or the Gemini Developer API (with `GEMINI_API_KEY`).

### Still models

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `imagen-4.0-generate-001` | Imagen 4 | Yes (up to 3 via Veo assets) | Default still model. High quality, photorealistic. |
| `imagen-4.0-ultra-generate-001` | Imagen 4 Ultra | Yes (up to 3 via Veo assets) | Higher quality variant. Slower generation. |
| `imagen-4.0-fast-generate-001` | Imagen 4 Fast | Yes (up to 3 via Veo assets) | Faster variant. Lower quality than standard. |
| `imagen-3.0-capability-001` | Imagen 3 Capability | Yes (single ref, edit mode) | Auto-selected when a single reference image is provided for style transfer. |

### Clip models

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `veo-3.1-fast-generate-001` | Veo 3.1 Fast | Yes (up to 3 asset refs) | Default clip model. Long-running operation, polled until complete. Audio disabled. |
| `veo-3.1-generate-001` | Veo 3.1 Standard | Yes (up to 3 asset refs) | Higher quality, slower generation. Audio disabled. |

### Safety

Google does not expose a safety tolerance toggle. Content filtering is handled server-side.

### Authentication

Google has two mutually exclusive auth paths. When `USE_VERTEX=true` is set, the API key is ignored entirely.

#### Option 1: Vertex AI (recommended for production)

Uses Google Cloud Application Default Credentials (ADC) — **not** an API key. The `.env` only sets the project and location; actual authentication comes from your `gcloud` login session.

```bash
# .env
USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_OUTPUT_BUCKET=gs://your-bucket-name/   # optional, for GCS video output
```

```bash
# Authenticate (run once per account)
gcloud auth application-default login

# To switch to a different Google account
gcloud auth application-default login --account other@gmail.com

# To use a different GCP project, change GOOGLE_CLOUD_PROJECT in .env
```

#### Option 2: Gemini Developer API (simpler setup)

Uses a plain API key. No `gcloud` CLI needed. Get a key from [Google AI Studio](https://aistudio.google.com/apikey).

```bash
# .env — do NOT set USE_VERTEX
GEMINI_API_KEY=your-api-key
```

To switch accounts, replace the API key with one from the other account.

#### Switching between projects

Each project directory has its own `.env`, so different storyboard projects can use different Google accounts or even different auth methods. Just configure each project's `.env` independently.

---

## FAL.ai (`backend: fal`)

FAL models are accessed via `fal-client`. Requires `FAL_KEY` in `.env`.

### Flux 1.x (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/flux-general` | Flux General | Yes (`reference_image_url`) | Supports LoRAs, ControlNets, reference images. Most versatile Flux model. |
| `fal-ai/flux-pro/v1.1` | Flux Pro 1.1 | Yes (`reference_image_url`) | High quality text-to-image. |

**Options:** `seed` (int), `num_inference_steps` (1–50), `guidance_scale` (0–20), `reference_strength` (float).

### Flux 2 (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/flux-2` | Flux 2 | **No** | Base Flux 2 model. Does not support `reference_image_url`. |
| `fal-ai/flux-2/turbo` | Flux 2 Turbo | **No** | Faster variant. Does not support references. |
| `fal-ai/flux-2/dev` | Flux 2 Dev | **No** | Development variant. Does not support references. |

**Options:** `seed` (int), `guidance_scale` (float), `acceleration` (string), `enable_prompt_expansion` (bool), `num_inference_steps` (int).

**Note:** If you provide reference images with a Flux 2 model, storyboard-gen logs a warning and proceeds without them. Use Flux 1.x (`flux-general`) or Kontext if you need reference support.

### Flux 2 Pro / Max (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/flux-2-pro` | Flux 2 Pro | Yes (multi-ref via `image_urls` + `/edit`) | Routes to `/edit` endpoint with refs; `@imageN` prompt syntax. |
| `fal-ai/flux-2-max` | Flux 2 Max | Yes (multi-ref via `image_urls` + `/edit`) | Higher quality variant of Flux 2 Pro. Same reference mechanism. |

Flux 2 Pro/Max support multi-reference stills via the `/edit` endpoint. When characters with reference images are present, storyboard-gen:
1. Uploads all character references to CDN
2. Rewrites `@character_id` tokens to `@imageN` (1-indexed, lowercase)
3. Routes to the `/edit` endpoint with `image_urls`

Without references, uses the base endpoint for text-to-image.

**Options:** `seed` (int), `guidance_scale` (float), `num_images` (int), `output_format` (string).

### Instant Character (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/instant-character` | Instant Character | Yes (single ref via `image_url`) | Character-consistent stills from a single reference image. |

Instant Character takes a single reference image via `image_url`. If multiple references are provided, the first existing file is used.

**Options:** `seed` (int), `num_images` (int), `output_format` (string).

### Kontext (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/flux-pro/kontext` | Kontext | Yes (`image_url` for i2i) | Auto-routes: image-to-image with reference, text-to-image without. |
| `fal-ai/flux-pro/kontext/max` | Kontext Max | Yes (`image_url` for i2i) | Higher quality variant. Same routing as Kontext. |
| `fal-ai/flux-pro/kontext/dev` | Kontext Dev | Yes (`image_url` for i2i) | Development variant. Same routing as Kontext. |

**Options:** `seed` (int), `guidance_scale` (float).

### Kontext Max Multi (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/flux-pro/kontext/max/multi` | Kontext Max Multi | Yes (multi-ref via `image_urls`) | Multiple reference images; model infers associations from context. |

Kontext Multi uses `aspect_ratio` directly (raw ratio strings). The model infers which reference maps to which subject from prompt context — no explicit `@ImageN` tags needed.

**Options:** `seed` (int), `guidance_scale` (float), `enhance_prompt` (bool).

### Kling O1 Image (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/kling-image/o1` | Kling O1 Image | Yes (multi-ref via `image_urls`) | Multi-character stills with `@ImageN` prompt syntax. |

O1 Image uses `aspect_ratio` directly (raw ratio strings, not `image_size` presets). Supports up to 10 reference images via `image_urls` with `@ImageN` prompt tokens for character mapping.

**Options:** `resolution` (`"1K"` or `"2K"`), `num_images` (int), `output_format` (string).

### Ideogram Character (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/ideogram/character` | Ideogram Character | Yes (dual-channel) | Separate character refs (`reference_image_urls`) and style refs (`image_urls`). |

Ideogram Character uses `image_size` presets (same mapping as Flux: `portrait_16_9`, etc.). It has two independent reference channels:

- **`reference_image_urls`**: Character identity references — sourced from scene `characters` with `reference` images.
- **`image_urls`**: Style/aesthetic references — sourced from the top-level `style_reference` field in `project.yaml`.

The model defaults to `style: "AUTO"` (overridable via `options.style`). No safety toggle is available.

**Options:** `style` (string, e.g. `"AUTO"`, `"GENERAL"`, `"REALISTIC"`, `"DESIGN"`), `seed` (int).

**Note:** If you configure `style_reference` but use a non-Ideogram model, storyboard-gen logs a warning and ignores the style references (see [reference warnings](#reference-image-warnings)).

### Ideogram V3 (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/ideogram/v3` | Ideogram V3 | Style refs only (`image_urls`) | Typography-focused. No character reference support. |

Ideogram V3 uses `image_size` presets. Supports style references via `image_urls` (same channel as Ideogram Character's style refs). Character references are **not supported** — only style/aesthetic references from `style_reference` in `project.yaml`.

**Options:** `style` (string, e.g. `"AUTO"`, `"GENERAL"`, `"REALISTIC"`, `"DESIGN"`), `seed` (int).

### Kling (clips)

| Model ID | Name | Notes |
|----------|------|-------|
| `fal-ai/kling-video/v2.1/pro/text-to-video` | Kling v2.1 Pro | Text-to-video. Auto-routes to i2v when `source_frame` is set. Audio disabled. |
| `fal-ai/kling-video/v2.1/pro/image-to-video` | Kling v2.1 Pro | Image-to-video. Auto-routes to t2v when no `source_frame`. Audio disabled. |
| `fal-ai/kling-video/v3/standard/image-to-video` | Kling v3 Standard | Different param names (`start_image_url`/`end_image_url`). Audio disabled. |
| `fal-ai/kling-video/o3/standard/image-to-video` | Kling O3 Standard | Supports character `elements[]` for multi-character consistency. Audio disabled. |
| `fal-ai/kling-video/o3/pro/text-to-video` | Kling O3 Pro | O3 with higher quality. Audio disabled. |

**Clip options:** `cfg_scale` (float), `negative_prompt` (string), `generate_audio` (bool, default false).

### Wan (clips)

| Model ID | Name | Notes |
|----------|------|-------|
| `fal-ai/wan-i2v` | Wan Image-to-Video | Image-to-video. Source frame via `image_url`. |
| `fal-ai/wan-pro/image-to-video` | Wan Pro | Higher quality image-to-video. |

Wan models are image-to-video only. Pass a `source_frame` in your scene config; storyboard-gen uploads it and passes it as `image_url`.

**Clip options:** Any model-specific options via the passthrough `options` dict.

### MiniMax (clips)

| Model ID | Name | Notes |
|----------|------|-------|
| `fal-ai/minimax/video-01-subject-reference` | MiniMax Subject Reference | Video with subject consistency from a reference image. |

MiniMax Subject Reference takes a single reference image via `subject_reference_image_url`. Use scene `reference` or character references — the first existing image is uploaded and passed to the API.

**Clip options:** Any model-specific options via the passthrough `options` dict.

### `@character_id` prompt syntax

Write `@character_id` tokens in scene prompts (e.g. `@boy`, `@mum`) using the character IDs from your `project.yaml`. The behaviour depends on the model:

| Model | Mapping | Description |
|-------|---------|-------------|
| Kling O3 clips | `@boy` → `@Element1` | Mapped to O3's character element system |
| Kling O1 Image stills | `@boy` → `@Image1` | Mapped to O1's image reference system |
| Flux 2 Pro/Max stills | `@boy` → `@image1` | Mapped to Flux 2 Pro's edit reference system (lowercase) |
| Kontext Max Multi stills | `@boy` → `boy` | `@` stripped; model infers from context |
| All other models | `@boy` → `boy` | `@` stripped; name remains as text |

When no `@character_id` tokens are present, O3, O1, and Flux 2 Pro auto-prepend `@TagN is <description>.` lines for each character.

**O3 clip example:**

```yaml
scenes:
  - number: 3
    type: clip
    duration: 5
    characters: [boy, mum]
    provider:
      backend: fal
      model: "fal-ai/kling-video/o3/standard/image-to-video"
    prompt: >
      @boy runs toward @mum who is standing at the door.
```

**O1 Image still example:**

```yaml
scenes:
  - number: 4
    type: still
    duration: 8
    ken_burns: "zoom_in"
    characters: [boy, sheep, collie]
    provider:
      backend: fal
      model: "fal-ai/kling-image/o1"
    prompt: >
      @boy kneels on a park path as @sheep leaps into his arms
      while @collie watches from behind.
```

**Flux 2 Pro still example:**

```yaml
scenes:
  - number: 5
    type: still
    duration: 6
    ken_burns: "pan_ltr"
    characters: [boy, mum]
    provider:
      backend: fal
      model: "fal-ai/flux-2-pro"
    prompt: >
      @boy and @mum walking through a sunlit garden.
```

### Options passthrough

The `options` field in provider config is a passthrough dict — any key/value pairs are merged directly into the API request. Use it for model-specific parameters like `seed`, `guidance_scale`, `num_inference_steps`, etc. Check the model's FAL API docs for supported parameters. If you pass something the model doesn't accept, you'll get an API error.

### Safety defaults

storyboard-gen injects safety defaults before merging user options, so user `options` always win:

| Model family | Default injected | Override via |
|--------------|-----------------|--------------|
| Flux 1.x / Flux 2 / Flux 2 Pro / Flux 2 Max | `enable_safety_checker: false` | `options.enable_safety_checker` |
| Instant Character | `enable_safety_checker: false` | `options.enable_safety_checker` |
| Kontext / Kontext Multi | `safety_tolerance: "6"` | `options.safety_tolerance` |
| Kling O1 Image | No toggle | — |
| Ideogram Character / V3 | No toggle | — |
| Kling clips | No default | — |
| Wan clips | No default | — |
| MiniMax clips | No default | — |

### Authentication

```bash
FAL_KEY=your-fal-key
```

---

## Replicate (`backend: replicate`)

Replicate models are accessed via the `replicate` SDK. Stills only — clips are not supported.

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `black-forest-labs/flux-1.1-pro` | Flux Pro 1.1 | No | Text-to-image only. |
| `black-forest-labs/flux-dev` | Flux Dev | Yes (`image` parameter) | Supports image-to-image with a single reference. |

**Options:** `seed` (int), `output_quality` (0–100), `prompt_upsampling` (bool).

### Safety defaults

| Default injected | Override via |
|-----------------|--------------|
| `safety_tolerance: 6` | `options.safety_tolerance` |

### Authentication

```bash
REPLICATE_API_TOKEN=your-replicate-token
```

---

## Reference image warnings

storyboard-gen checks for reference/model mismatches and logs warnings. These warnings appear during both `--dry-run` and real generation:

| Condition | Warning |
|-----------|---------|
| `style_reference` configured but model is not Ideogram (Character or V3) | Style references will be ignored |
| Character or scene references configured but model is Flux 2 | References will be ignored |

---

## Choosing a model

### For stills

| Need | Recommended model | Why |
|------|-------------------|-----|
| Best quality, no references | `imagen-4.0-generate-001` (Google) | Strongest photorealistic output |
| Fastest Google | `imagen-4.0-fast-generate-001` (Google) | Same quality tier, faster generation |
| Reference image consistency | `fal-ai/flux-general` (FAL) | Best reference support with LoRAs |
| Multi-character with refs | `fal-ai/flux-2-pro` (FAL) | Multi-ref via `@imageN` + `/edit` endpoint |
| Character from single ref | `fal-ai/instant-character` (FAL) | Purpose-built for character consistency |
| Multi-character consistency | `fal-ai/kling-image/o1` (FAL) | `@ImageN` mapping + `image_urls` |
| Multi-ref, implicit mapping | `fal-ai/flux-pro/kontext/max/multi` (FAL) | Model infers associations |
| Style transfer from a reference | `fal-ai/flux-pro/kontext` (FAL) | Purpose-built for image-to-image |
| Character + style refs | `fal-ai/ideogram/character` (FAL) | Dual-channel: identity + aesthetic |
| Typography | `fal-ai/ideogram/v3` (FAL) | Best text rendering in images |
| Fast iteration | `fal-ai/flux-2/turbo` (FAL) | Fastest generation time |
| No API key setup | `black-forest-labs/flux-dev` (Replicate) | Simple token-based auth |

### For clips

| Need | Recommended model | Why |
|------|-------------------|-----|
| Best quality | `veo-3.1-fast-generate-001` (Google) | Most capable video model |
| Higher quality Google | `veo-3.1-generate-001` (Google) | Standard (non-fast) Veo |
| Multi-character consistency | `fal-ai/kling-video/o3/*/image-to-video` (FAL) | Character elements support |
| Image-to-video | Any Kling model with `source_frame` | Auto-routes endpoint |
| Subject reference video | `fal-ai/minimax/video-01-subject-reference` (FAL) | Subject consistency from ref image |
| Image-to-video (Wan) | `fal-ai/wan-i2v` (FAL) | Simple i2v from source frame |

---

## Provider comparison

| Feature | Google | FAL (Flux 1.x) | FAL (Flux 2) | FAL (Flux 2 Pro/Max) | FAL (Kontext) | FAL (Kontext Multi) | FAL (O1 Image) | FAL (Instant Char) | FAL (Ideogram Char) | FAL (Ideogram V3) | FAL (Kling clips) | FAL (Wan clips) | FAL (MiniMax clips) | Replicate |
|---------|--------|-----------------|--------------|----------------------|---------------|---------------------|----------------|---------------------|---------------------|-------------------|-------------------|-----------------|---------------------|-----------|
| Stills | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes | No | No | No | Yes |
| Clips | Yes (Veo) | No | No | No | No | No | No | No | No | No | Yes | Yes | Yes | No |
| Reference images | Yes (up to 3) | Yes (1) | **No** | Yes (multi, `@imageN`) | Yes (1, i2i) | Yes (multi) | Yes (multi, `@ImageN`) | Yes (1) | Yes (dual-channel) | Style only | N/A | N/A | Yes (1, subject) | Yes (1) |
| Style references | No | No | No | No | No | No | No | No | Yes (`image_urls`) | Yes (`image_urls`) | No | No | No | No |
| Safety toggle | No | Yes | Yes | Yes | Yes | Yes | No | Yes | No | No | No | No | No | Yes |
| Character elements | No | No | No | No | No | No | No | No | No | No | Yes (O3) | No | No | No |
| Audio disabled | Yes | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | Yes | N/A | N/A | N/A |
| Auth method | GCP / API key | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | Token |

---

## See also

- [project-yaml-spec.md](project-yaml-spec.md) — complete `project.yaml` schema with provider configuration examples
- [architecture.md](architecture.md) — how providers are resolved and how generation works
- [VISION.md](VISION.md) — project goals and non-goals
