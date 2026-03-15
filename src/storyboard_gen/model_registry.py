# ABOUTME: Centralized registry of known backends and their common models.
# ABOUTME: Used by the GUI project settings form for cascading dropdowns.

from __future__ import annotations

# Known models per backend, kept in sync with docs/models.md.
# test_model_registry.py verifies this list matches the documentation.
# Listed in rough order: stills first, then clips, by popularity.
BACKEND_MODELS: dict[str, list[str]] = {
    "google": [
        # Stills
        "imagen-4.0-generate-001",
        "imagen-4.0-fast-generate-001",
        "imagen-4.0-ultra-generate-001",
        "imagen-3.0-capability-001",
        # Clips
        "veo-3.1-fast-generate-001",
        "veo-3.1-generate-001",
    ],
    "fal": [
        # Flux 1.x stills
        "fal-ai/flux-general",
        "fal-ai/flux-pro/v1.1",
        "fal-ai/flux/dev",
        # Flux 2 stills
        "fal-ai/flux-2",
        "fal-ai/flux-2/turbo",
        "fal-ai/flux-2/dev",
        "fal-ai/flux-2/flash",
        "fal-ai/flux-2-flex",
        # Flux 2 Pro / Max stills
        "fal-ai/flux-2-pro",
        "fal-ai/flux-2-max",
        # Instant Character stills
        "fal-ai/instant-character",
        # Kontext stills
        "fal-ai/flux-pro/kontext",
        "fal-ai/flux-pro/kontext/max",
        "fal-ai/flux-kontext/dev",
        "fal-ai/flux-pro/kontext/max/multi",
        # Kling O1 Image stills
        "fal-ai/kling-image/o1",
        # Ideogram stills
        "fal-ai/ideogram/character",
        "fal-ai/ideogram/v3",
        # Grok stills (xAI)
        "xai/grok-imagine-image",
        "xai/grok-imagine-image/edit",
        # Seedream stills (ByteDance)
        "fal-ai/bytedance/seedream/v4.5/text-to-image",
        "fal-ai/bytedance/seedream/v4.5/edit",
        "fal-ai/bytedance/seedream/v5/lite/text-to-image",
        # Hunyuan Image stills (Tencent)
        "fal-ai/hunyuan-image/v3/text-to-image",
        # Recraft stills
        "fal-ai/recraft/v4/text-to-image",
        # Qwen Image stills (Alibaba)
        "fal-ai/qwen-image-2512",
        # GLM Image stills (Zhipu)
        "fal-ai/glm-image",
        # Nano Banana stills
        "fal-ai/nano-banana-2",
        # Kling clips
        "fal-ai/kling-video/v2.1/pro/text-to-video",
        "fal-ai/kling-video/v2.1/pro/image-to-video",
        "fal-ai/kling-video/v3/standard/image-to-video",
        "fal-ai/kling-video/o3/standard/image-to-video",
        "fal-ai/kling-video/o3/pro/text-to-video",
        # Grok clips (xAI)
        "xai/grok-imagine-video/text-to-video",
        "xai/grok-imagine-video/image-to-video",
        # Seedance clips (ByteDance)
        "fal-ai/bytedance/seedance/v1.5/pro/text-to-video",
        "fal-ai/bytedance/seedance/v1.5/pro/image-to-video",
        # Hunyuan Video clips (Tencent)
        "fal-ai/hunyuan-video-v1.5/text-to-video",
        "fal-ai/hunyuan-video-v1.5/image-to-video",
        # Wan clips
        "fal-ai/wan-i2v",
        "fal-ai/wan-pro/image-to-video",
        "wan/v2.6/text-to-video",
        "wan/v2.6/image-to-video",
        # MiniMax clips
        "fal-ai/minimax/video-01-subject-reference",
    ],
    "replicate": [
        "black-forest-labs/flux-1.1-pro",
        "black-forest-labs/flux-dev",
    ],
}


def get_backends() -> list[str]:
    """Return list of known backend names."""
    return list(BACKEND_MODELS.keys())


def get_models_for_backend(backend: str) -> list[str]:
    """Return known models for a backend, or empty list if unknown."""
    return BACKEND_MODELS.get(backend, [])


def get_all_models() -> dict[str, str]:
    """Return {model_id: backend} for all known models across all backends."""
    return {m: b for b, models in BACKEND_MODELS.items() for m in models}
