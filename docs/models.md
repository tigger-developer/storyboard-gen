<!-- Version: 3.3 | Last updated: 2026-03-12 -->

# Model Reference

Comprehensive guide to all AI models supported by storyboard-gen, organised by provider.

**Audio on clips:** All clip providers disable audio generation by default where a toggle is available. Google Veo sets `generate_audio=False`; FAL Kling and Seedance set `generate_audio: false`. Grok video and Hunyuan video have no audio toggle (Grok generates audio inherently; Hunyuan has no audio support). This prevents unwanted AI-generated audio from interfering with your project's audio track.

**Cost estimates:** Pricing is available via `--dry-run` (CLI) and in the GUI scene list and generate dialog. Pricing lookup follows a priority chain: project.yaml override > FAL live API > static defaults. FAL models use the FAL pricing API (session-cached). Google models (Imagen, Veo) use built-in static defaults. You can override pricing for any provider in `project.yaml`:

```yaml
providers:
  still:
    backend: fal
    model: fal-ai/flux-pro/v1.1
    pricing:
      unit_price: 0.05
      unit: image
      # currency defaults to USD
```

**Pricing note:** Cost estimates are indicative. FAL prices are fetched live from the FAL pricing API. Google and Replicate prices are static defaults that may be outdated. Google pricing is from the [Gemini API pricing page](https://ai.google.dev/gemini-api/docs/pricing); Replicate pricing is from [replicate.com/pricing](https://replicate.com/pricing) as of 2026-03-11. Use `--dry-run` for current estimates, or override per model in `project.yaml`.

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
| `fal-ai/flux-dev` | Flux Dev | Yes (`reference_image_url`) | Non-commercial licence. Cheaper alternative to Flux Pro (~$0.025/image vs $0.04). |

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

### Grok Imagine Image (stills) — xAI

| Model ID | Name | Price | Reference support | Notes |
|----------|------|-------|-------------------|-------|
| `xai/grok-imagine-image` | Grok Imagine Image | ~$0.02/image | Yes (edit endpoint, `image_urls` max 3) | Cheapest still option. Good quality. Uses raw `aspect_ratio` strings. |
| `xai/grok-imagine-image/edit` | Grok Imagine Image Edit | ~$0.022/image | Yes (`image_urls`) | Image editing variant. |

Grok Image uses raw `aspect_ratio` strings (not `image_size` presets). Wide range of aspect ratios supported: `2:1`, `20:9`, `19.5:9`, `16:9`, `4:3`, `3:2`, `1:1`, `2:3`, `3:4`, `9:16`, `9:19.5`, `9:20`, `1:2`.

When characters with reference images are present, storyboard-gen routes to the `/edit` endpoint with `image_urls` (max 3). Without references, uses the base text-to-image endpoint.

**Options:** `num_images` (int), `output_format` (`"jpeg"`, `"png"`, `"webp"`).

**Note:** No `enable_safety_checker`, `seed`, or `safety_tolerance` parameters are available.

### Seedream (stills) — ByteDance

| Model ID | Name | Price | Reference support | Notes |
|----------|------|-------|-------------------|-------|
| `fal-ai/bytedance/seedream/v4.5/text-to-image` | Seedream 4.5 | ~$0.04/image | No (t2i) | Strong quality, 4K support (`auto_2K`, `auto_4K` presets). |
| `fal-ai/bytedance/seedream/v4.5/edit` | Seedream 4.5 Edit | ~$0.04/image | Yes (`image_urls` up to 10) | Multi-reference editing. |
| `fal-ai/bytedance/seedream/v5/lite/text-to-image` | Seedream v5 Lite | ~$0.04/image | No | Latest model. Web search + reasoning. |

Seedream uses `image_size` presets. When characters with reference images are present, v4.5 routes to the `/edit` endpoint with `image_urls`. Seedream v5 Lite has no edit endpoint.

**Options:** `seed` (int), `num_images` (int), `max_images` (int).

### Hunyuan Image (stills) — Tencent

| Model ID | Name | Price | Reference support | Notes |
|----------|------|-------|-------------------|-------|
| `fal-ai/hunyuan-image/v3/text-to-image` | Hunyuan Image V3 | TBC | No | 80B MoE model. Rich diffusion parameters. |

Hunyuan Image uses `image_size` presets. No reference image support. Supports detailed control via diffusion parameters.

**Options:** `guidance_scale` (float, default 7.5), `num_inference_steps` (int, default 28), `negative_prompt` (string), `enable_prompt_expansion` (bool), `seed` (int), `output_format` (`"jpeg"`, `"png"`).

### Recraft (stills)

| Model ID | Name | Price | Reference support | Notes |
|----------|------|-------|-------------------|-------|
| `fal-ai/recraft/v4/text-to-image` | Recraft V4 | ~$0.04/image | No | Design-focused. Colour palette control. |

Recraft uses `image_size` presets. Notable for its colour control parameters.

**Options:** `colors` (list of `{r, g, b}` RGB objects), `background_color` (`{r, g, b}` RGB object).

### Kling (clips)

| Model ID | Name | Notes |
|----------|------|-------|
| `fal-ai/kling-video/v2.1/pro/text-to-video` | Kling v2.1 Pro | Text-to-video. Auto-routes to i2v when `source_frame` is set. Audio disabled. |
| `fal-ai/kling-video/v2.1/pro/image-to-video` | Kling v2.1 Pro | Image-to-video. Auto-routes to t2v when no `source_frame`. Audio disabled. |
| `fal-ai/kling-video/v3/standard/image-to-video` | Kling v3 Standard | Different param names (`start_image_url`/`end_image_url`). Audio disabled. |
| `fal-ai/kling-video/o3/standard/image-to-video` | Kling O3 Standard | Supports character `elements[]` for multi-character consistency. Audio disabled. |
| `fal-ai/kling-video/o3/pro/text-to-video` | Kling O3 Pro | O3 with higher quality. Audio disabled. |

**Clip options:** `cfg_scale` (float), `negative_prompt` (string), `generate_audio` (bool, default false).

### Grok Imagine Video (clips) — xAI

| Model ID | Name | Price | Notes |
|----------|------|-------|-------|
| `xai/grok-imagine-video/text-to-video` | Grok Video T2V | ~$0.05–0.07/s | Very fast (~17s), up to 15s. Native audio (no toggle). |
| `xai/grok-imagine-video/image-to-video` | Grok Video I2V | ~$0.05–0.07/s | I2V with native audio. `image_url` from `source_frame`. |

Grok video uses `duration` as an integer (1–15 seconds), `aspect_ratio` as raw strings, and `resolution` (`480p`/`720p`). Auto-routes between t2v and i2v based on `source_frame`.

**Note:** Grok video generates audio inherently with no toggle to disable it. This differs from other clip models.

**Clip options:** `resolution` (`"480p"`, `"720p"`).

### Seedance (clips) — ByteDance

| Model ID | Name | Price | Notes |
|----------|------|-------|-------|
| `fal-ai/bytedance/seedance/v1.5/pro/text-to-video` | Seedance 1.5 Pro T2V | ~$0.26/5s | Native audio (disabled by default), 1080p, 4–12s. |
| `fal-ai/bytedance/seedance/v1.5/pro/image-to-video` | Seedance 1.5 Pro I2V | ~$0.26/5s | I2V with `image_url` + optional `end_image_url`. |

Seedance uses `duration` as a string enum (`"4"` through `"12"`), `aspect_ratio` as raw strings, and `resolution` (`480p`/`720p`/`1080p`). Supports `camera_fixed` (boolean) to lock camera position, and `end_image_url` for end-frame control on i2v. Audio disabled by default (`generate_audio: false`), safety checker disabled (`enable_safety_checker: false`). Auto-routes between t2v and i2v based on `source_frame`.

**Clip options:** `resolution` (`"480p"`, `"720p"`, `"1080p"`), `camera_fixed` (bool), `seed` (int), `generate_audio` (bool).

### Hunyuan Video (clips) — Tencent

| Model ID | Name | Price | Notes |
|----------|------|-------|-------|
| `fal-ai/hunyuan-video-v1.5/text-to-video` | Hunyuan Video 1.5 T2V | ~$0.075/s | Solid quality, competitive price. |
| `fal-ai/hunyuan-video-v1.5/image-to-video` | Hunyuan Video 1.5 I2V | ~$0.075/s | I2V with `image_url`. |

Hunyuan Video uses `aspect_ratio` (only `16:9` and `9:16` supported) and `num_frames` (integer, default 121) instead of a `duration` parameter. Resolution is fixed to `480p`. No audio support, no safety toggle. Auto-routes between t2v and i2v based on `source_frame`.

**Clip options:** `num_frames` (int, 1–121), `num_inference_steps` (int, 1–50), `negative_prompt` (string), `seed` (int), `enable_prompt_expansion` (bool).

### Wan (clips)

| Model ID | Name | Price | Notes |
|----------|------|-------|-------|
| `fal-ai/wan-i2v` | Wan Image-to-Video | — | Image-to-video. Source frame via `image_url`. |
| `fal-ai/wan-pro/image-to-video` | Wan Pro | — | Higher quality image-to-video. |
| `wan/v2.6/text-to-video` | Wan 2.6 T2V | ~$0.10–0.15/s | Multi-shot, native audio via `audio_url`, 1080p, 5/10/15s. |
| `wan/v2.6/image-to-video` | Wan 2.6 I2V | ~$0.10–0.15/s | I2V with native audio, 1080p. |

Wan 2.6 uses `duration` as a string enum (`"5"`, `"10"`, `"15"`), `aspect_ratio` as raw strings, and `resolution` (`720p`/`1080p`). Supports `audio_url` for background music (not auto-generation) and `multi_shots` for narrative segmentation. Safety checker disabled by default.

**Note:** Wan 2.6 models use a `wan/` prefix (not `fal-ai/`). This is handled automatically.

**Clip options:** `resolution` (`"720p"`, `"1080p"`), `audio_url` (string), `multi_shots` (bool), `enable_prompt_expansion` (bool), `negative_prompt` (string), `seed` (int).

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
| Seedream (all) | `enable_safety_checker: false` | `options.enable_safety_checker` |
| Hunyuan Image | `enable_safety_checker: false` | `options.enable_safety_checker` |
| Recraft | `enable_safety_checker: false` | `options.enable_safety_checker` |
| Kontext / Kontext Multi | `safety_tolerance: "6"` | `options.safety_tolerance` |
| Grok Image | No toggle | — |
| Kling O1 Image | No toggle | — |
| Ideogram Character / V3 | No toggle | — |
| Grok clips | No toggle | — |
| Seedance clips | `generate_audio: false`, `enable_safety_checker: false` | `options.*` |
| Hunyuan Video clips | No toggle | — |
| Wan 2.6 clips | `enable_safety_checker: false` | `options.enable_safety_checker` |
| Kling clips | No default | — |
| Wan (legacy) clips | No default | — |
| MiniMax clips | No default | — |

### Authentication

```bash
FAL_KEY=your-fal-key
```

---

## Replicate (`backend: replicate`)

Replicate models are accessed via the `replicate` SDK. Stills only — clips are not supported.

| Model ID | Name | Price | Reference support | Notes |
|----------|------|-------|-------------------|-------|
| `black-forest-labs/flux-1.1-pro` | Flux Pro 1.1 | $0.04/image | No | Text-to-image only. |
| `black-forest-labs/flux-dev` | Flux Dev | $0.025/image | Yes (`image` parameter) | Supports image-to-image with a single reference. Non-commercial licence. |

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
| Cheapest option | `xai/grok-imagine-image` (FAL/xAI) | ~$0.02/image, good quality |
| Reference image consistency | `fal-ai/flux-general` (FAL) | Best reference support with LoRAs |
| Multi-character with refs | `fal-ai/flux-2-pro` (FAL) | Multi-ref via `@imageN` + `/edit` endpoint |
| Character from single ref | `fal-ai/instant-character` (FAL) | Purpose-built for character consistency |
| Multi-character consistency | `fal-ai/kling-image/o1` (FAL) | `@ImageN` mapping + `image_urls` |
| Multi-ref, implicit mapping | `fal-ai/flux-pro/kontext/max/multi` (FAL) | Model infers associations |
| Style transfer from a reference | `fal-ai/flux-pro/kontext` (FAL) | Purpose-built for image-to-image |
| Character + style refs | `fal-ai/ideogram/character` (FAL) | Dual-channel: identity + aesthetic |
| Typography | `fal-ai/ideogram/v3` (FAL) | Best text rendering in images |
| Design with colour control | `fal-ai/recraft/v4/text-to-image` (FAL) | RGB palette control |
| 4K resolution | `fal-ai/bytedance/seedream/v4.5/text-to-image` (FAL) | Supports `auto_4K` preset |
| Fast iteration | `fal-ai/flux-2/turbo` (FAL) | Fastest generation time |
| Budget with refs (non-commercial) | `fal-ai/flux-dev` (FAL) | ~$0.025/image, reference support, non-commercial licence |
| No API key setup | `black-forest-labs/flux-dev` (Replicate) | Simple token-based auth |

### For clips

| Need | Recommended model | Why |
|------|-------------------|-----|
| Best quality | `veo-3.1-fast-generate-001` (Google) | Most capable video model |
| Higher quality Google | `veo-3.1-generate-001` (Google) | Standard (non-fast) Veo |
| Fastest generation | `xai/grok-imagine-video/text-to-video` (FAL/xAI) | ~17s generation, up to 15s clips |
| Cheapest clips | `xai/grok-imagine-video/text-to-video` (FAL/xAI) | ~$0.05–0.07/s |
| 1080p resolution | `fal-ai/bytedance/seedance/v1.5/pro/text-to-video` (FAL) | Supports 1080p |
| Multi-character consistency | `fal-ai/kling-video/o3/*/image-to-video` (FAL) | Character elements support |
| Multi-shot narratives | `wan/v2.6/text-to-video` (FAL) | `multi_shots` for scene segmentation |
| End-frame control | `fal-ai/bytedance/seedance/v1.5/pro/image-to-video` (FAL) | `end_image_url` support |
| Image-to-video | Any model with `source_frame` | Auto-routes endpoint |
| Subject reference video | `fal-ai/minimax/video-01-subject-reference` (FAL) | Subject consistency from ref image |
| Competitive price | `fal-ai/hunyuan-video-v1.5/text-to-video` (FAL) | ~$0.075/s |

---

## Provider comparison

### Still models

| Model family | Reference support | Safety toggle | Aspect ratio | Auth |
|-------------|-------------------|---------------|-------------|------|
| Google Imagen | Yes (up to 3 refs) | No | N/A | GCP / API key |
| FAL Flux 1.x | Yes (1 ref) | `enable_safety_checker` | `image_size` presets | FAL_KEY |
| FAL Flux 2 | **No** | `enable_safety_checker` | `image_size` presets | FAL_KEY |
| FAL Flux 2 Pro/Max | Yes (multi, `@imageN`) | `enable_safety_checker` | `image_size` presets | FAL_KEY |
| FAL Kontext | Yes (1 ref, i2i) | `safety_tolerance` | Raw strings (i2i) / presets (t2i) | FAL_KEY |
| FAL Kontext Multi | Yes (multi) | `safety_tolerance` | Raw strings | FAL_KEY |
| FAL O1 Image | Yes (multi, `@ImageN`) | No | Raw strings | FAL_KEY |
| FAL Instant Character | Yes (1 ref) | `enable_safety_checker` | `image_size` presets | FAL_KEY |
| FAL Ideogram Character | Yes (dual-channel) | No | `image_size` presets | FAL_KEY |
| FAL Ideogram V3 | Style refs only | No | `image_size` presets | FAL_KEY |
| FAL Grok Image (xAI) | Yes (edit, max 3) | No | Raw strings | FAL_KEY |
| FAL Seedream (ByteDance) | Yes (edit, v4.5) | `enable_safety_checker` | `image_size` presets | FAL_KEY |
| FAL Hunyuan Image (Tencent) | No | `enable_safety_checker` | `image_size` presets | FAL_KEY |
| FAL Recraft | No | `enable_safety_checker` | `image_size` presets | FAL_KEY |
| Replicate Flux | Yes (1 ref, some models) | `safety_tolerance` | N/A | Token |

### Clip models

| Model family | Price | Audio toggle | Auto-route t2v↔i2v | Source frame | Auth |
|-------------|-------|-------------|---------------------|-------------|------|
| Google Veo | N/A | `generate_audio` (disabled) | No | N/A | GCP / API key |
| FAL Kling | N/A | `generate_audio` (disabled) | Yes | `image_url` | FAL_KEY |
| FAL Grok Video (xAI) | ~$0.05–0.07/s | No toggle (always on) | Yes | `image_url` | FAL_KEY |
| FAL Seedance (ByteDance) | ~$0.26/5s | `generate_audio` (disabled) | Yes | `image_url` + `end_image_url` | FAL_KEY |
| FAL Hunyuan Video (Tencent) | ~$0.075/s | No (no audio) | Yes | `image_url` | FAL_KEY |
| FAL Wan 2.6 (Alibaba) | ~$0.10–0.15/s | `audio_url` (supply your own) | No | `image_url` | FAL_KEY |
| FAL Wan (legacy) | N/A | N/A | No | `image_url` | FAL_KEY |
| FAL MiniMax | N/A | N/A | No | `subject_reference_image_url` | FAL_KEY |

---

## See also

- [project-yaml-spec.md](project-yaml-spec.md) — complete `project.yaml` schema with provider configuration examples
- [architecture.md](architecture.md) — how providers are resolved and how generation works
- [VISION.md](VISION.md) — project goals and non-goals
