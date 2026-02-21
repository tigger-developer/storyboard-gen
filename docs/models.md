<!-- Version: 1.3 | Last updated: 2026-02-21 -->

# Model Reference

Comprehensive guide to all AI models supported by storyboard-gen, organised by provider.

---

## Google (`backend: google`)

Google models are accessed via Vertex AI (with GCP credentials) or the Gemini Developer API (with `GEMINI_API_KEY`).

### Still models

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `imagen-4.0-generate-001` | Imagen 4 | Yes (up to 3 via Veo assets) | Default still model. High quality, photorealistic. |
| `imagen-3.0-capability-001` | Imagen 3 Capability | Yes (single ref, edit mode) | Auto-selected when a single reference image is provided for style transfer. |

### Clip models

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `veo-3.1-fast-generate-001` | Veo 3.1 Fast | Yes (up to 3 asset refs) | Default clip model. Long-running operation, polled until complete. |

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

**Options:** `seed` (int), `safety_tolerance` (1–6), `num_inference_steps` (1–50), `guidance_scale` (0–20), `reference_strength` (float).

### Flux 2 (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/flux-2` | Flux 2 | **No** | Base Flux 2 model. Does not support `reference_image_url`. |
| `fal-ai/flux-2/turbo` | Flux 2 Turbo | **No** | Faster variant. Does not support references. |
| `fal-ai/flux-2/dev` | Flux 2 Dev | **No** | Development variant. Does not support references. |

Flux 2 models use a different safety parameter (`enable_safety_checker` boolean) instead of `safety_tolerance`.

**Options:** `seed` (int), `enable_safety_checker` (bool), `guidance_scale` (float), `acceleration` (string), `enable_prompt_expansion` (bool), `num_inference_steps` (int).

**Note:** If you provide reference images with a Flux 2 model, storyboard-gen logs a warning and proceeds without them. Use Flux 1.x (`flux-general`) or Kontext if you need reference support.

### Kontext (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/flux-pro/kontext` | Kontext | Yes (`image_url` for i2i) | Auto-routes: image-to-image with reference, text-to-image without. |

Kontext uses `safety_tolerance` (string, "1"–"6") like Flux 1.x.

**Options:** `seed` (int), `safety_tolerance` (string, "1"–"6"), `guidance_scale` (float).

### Kling O1 Image (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/kling-image/o1` | Kling O1 Image | Yes (multi-ref via `image_urls` + `elements[]`) | Multi-character stills with `@ImageN` prompt syntax. |

O1 Image uses `aspect_ratio` directly (raw ratio strings, not `image_size` presets). Supports up to 10 reference images via `image_urls` and character elements for multi-reference consistency.

**Options:** `resolution` (`"1K"` or `"2K"`), `num_images` (int), `output_format` (string).

### Kontext Max Multi (stills)

| Model ID | Name | Reference support | Notes |
|----------|------|-------------------|-------|
| `fal-ai/flux-pro/kontext/max/multi` | Kontext Max Multi | Yes (multi-ref via `image_urls`) | Multiple reference images; model infers associations from context. |

Kontext Multi uses `aspect_ratio` directly (raw ratio strings). The model infers which reference maps to which subject from prompt context — no explicit `@ImageN` tags needed.

**Options:** `seed` (int), `safety_tolerance` (string, "1"–"6"), `guidance_scale` (float), `enhance_prompt` (bool).

### Kling (clips)

| Model ID | Name | Notes |
|----------|------|-------|
| `fal-ai/kling-video/v2.1/pro/text-to-video` | Kling v2.1 Pro | Text-to-video. Auto-routes to i2v when `source_frame` is set. |
| `fal-ai/kling-video/v2.1/pro/image-to-video` | Kling v2.1 Pro | Image-to-video. Auto-routes to t2v when no `source_frame`. |
| `fal-ai/kling-video/v3/standard/image-to-video` | Kling v3 Standard | Different param names (`start_image_url`/`end_image_url`). |
| `fal-ai/kling-video/o3/standard/image-to-video` | Kling O3 Standard | Supports character `elements[]` for multi-character consistency. |
| `fal-ai/kling-video/o3/pro/text-to-video` | Kling O3 Pro | O3 with higher quality. |

**Clip options:** `cfg_scale` (float), `negative_prompt` (string), `generate_audio` (bool, default false).

### `@character_id` prompt syntax

Write `@character_id` tokens in scene prompts (e.g. `@boy`, `@mum`) using the character IDs from your `project.yaml`. The behaviour depends on the model:

| Model | Mapping | Description |
|-------|---------|-------------|
| Kling O3 clips | `@boy` → `@Element1` | Mapped to O3's character element system |
| Kling O1 Image stills | `@boy` → `@Image1` | Mapped to O1's image reference system |
| Kontext Max Multi stills | `@boy` → `boy` | `@` stripped; model infers from context |
| All other models | `@boy` → `boy` | `@` stripped; name remains as text |

When no `@character_id` tokens are present, O3 and O1 auto-prepend `@ElementN is <description>.` / `@ImageN is <description>.` lines for each character.

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

### Safety defaults

storyboard-gen injects safety defaults before merging user options, so user `options` always win:

| Model family | Default injected | Override via |
|--------------|-----------------|--------------|
| Flux 1.x / Flux 2 | `enable_safety_checker: false` | `options.enable_safety_checker` |
| Kontext / Kontext Multi | `safety_tolerance: "6"` | `options.safety_tolerance` |
| Kling O1 Image | `enable_safety_checker: false` | `options.enable_safety_checker` |
| Kling clips | No default | — |

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

**Options:** `seed` (int), `safety_tolerance` (0–6), `output_quality` (0–100), `prompt_upsampling` (bool).

### Safety defaults

| Default injected | Override via |
|-----------------|--------------|
| `safety_tolerance: 6` | `options.safety_tolerance` |

### Authentication

```bash
REPLICATE_API_TOKEN=your-replicate-token
```

---

## Choosing a model

### For stills

| Need | Recommended model | Why |
|------|-------------------|-----|
| Best quality, no references | `imagen-4.0-generate-001` (Google) | Strongest photorealistic output |
| Reference image consistency | `fal-ai/flux-general` (FAL) | Best reference support with LoRAs |
| Multi-character consistency | `fal-ai/kling-image/o1` (FAL) | `@ImageN` mapping + `elements[]` |
| Multi-ref, implicit mapping | `fal-ai/flux-pro/kontext/max/multi` (FAL) | Model infers associations |
| Style transfer from a reference | `fal-ai/flux-pro/kontext` (FAL) | Purpose-built for image-to-image |
| Fast iteration | `fal-ai/flux-2/turbo` (FAL) | Fastest generation time |
| No API key setup | `black-forest-labs/flux-dev` (Replicate) | Simple token-based auth |

### For clips

| Need | Recommended model | Why |
|------|-------------------|-----|
| Best quality | `veo-3.1-fast-generate-001` (Google) | Most capable video model |
| Multi-character consistency | `fal-ai/kling-video/o3/*/image-to-video` (FAL) | Character elements support |
| Image-to-video | Any Kling model with `source_frame` | Auto-routes endpoint |

---

## Provider comparison

| Feature | Google | FAL (Flux 1.x) | FAL (Flux 2) | FAL (Kontext) | FAL (Kontext Multi) | FAL (O1 Image) | FAL (Kling clips) | Replicate |
|---------|--------|-----------------|--------------|---------------|---------------------|----------------|-------------------|-----------|
| Stills | Yes | Yes | Yes | Yes | Yes | Yes | No | Yes |
| Clips | Yes (Veo) | No | No | No | No | No | Yes | No |
| Reference images | Yes (up to 3) | Yes (1) | **No** | Yes (1, i2i) | Yes (multi) | Yes (multi, `@ImageN`) | N/A | Yes (1) |
| Safety toggle | No | Yes | Yes | Yes | Yes | Yes | No | Yes |
| Character elements | No | No | No | No | No | Yes (`elements[]`) | Yes (O3) | No |
| Auth method | GCP / API key | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | Token |
