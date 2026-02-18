<!-- Version: 1.0 | Last updated: 2026-02-18 -->

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

```bash
# Vertex AI (recommended for production)
USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GCS_OUTPUT_BUCKET=gs://your-bucket-name/

# OR Gemini Developer API
GEMINI_API_KEY=your-api-key
```

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

### Kling (clips)

| Model ID | Name | Notes |
|----------|------|-------|
| `fal-ai/kling-video/v2.1/pro/text-to-video` | Kling v2.1 Pro | Text-to-video. Auto-routes to i2v when `source_frame` is set. |
| `fal-ai/kling-video/v2.1/pro/image-to-video` | Kling v2.1 Pro | Image-to-video. Auto-routes to t2v when no `source_frame`. |
| `fal-ai/kling-video/v3/standard/image-to-video` | Kling v3 Standard | Different param names (`start_image_url`/`end_image_url`). |
| `fal-ai/kling-video/o3/standard/image-to-video` | Kling O3 Standard | Supports character `elements[]` for multi-character consistency. |
| `fal-ai/kling-video/o3/pro/text-to-video` | Kling O3 Pro | O3 with higher quality. |

**Clip options:** `cfg_scale` (float), `negative_prompt` (string), `generate_audio` (bool, default false).

### Safety defaults

storyboard-gen injects safety defaults before merging user options, so user `options` always win:

| Model family | Default injected | Override via |
|--------------|-----------------|--------------|
| Flux 1.x / Flux 2 | `enable_safety_checker: false` | `options.enable_safety_checker` |
| Kontext | `safety_tolerance: "6"` | `options.safety_tolerance` |
| Kling | No default | — |

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

| Feature | Google | FAL (Flux 1.x) | FAL (Flux 2) | FAL (Kontext) | FAL (Kling) | Replicate |
|---------|--------|-----------------|--------------|---------------|-------------|-----------|
| Stills | Yes | Yes | Yes | Yes | No | Yes |
| Clips | Yes (Veo) | No | No | No | Yes | No |
| Reference images | Yes (up to 3) | Yes (1) | **No** | Yes (1, i2i) | N/A | Yes (1) |
| Safety toggle | No | Yes | Yes | Yes | No | Yes |
| Character elements | No | No | No | No | Yes (O3) | No |
| Auth method | GCP / API key | FAL_KEY | FAL_KEY | FAL_KEY | FAL_KEY | Token |
