# ABOUTME: Centralized registry of known backends and their common models.
# ABOUTME: Used by the GUI project settings form for cascading dropdowns.

from __future__ import annotations

# Known models per backend. Not exhaustive — users can type custom model IDs.
# Listed in rough order of popularity/recommendation.
BACKEND_MODELS: dict[str, list[str]] = {
    "google": [
        "imagen-4.0-generate-001",
        "imagen-4.0-fast-generate-001",
        "imagen-4.0-ultra-generate-001",
        "imagen-3.0-capability-001",
        "veo-3.1-fast-generate-001",
        "veo-3.1-generate-001",
        "veo-3.0-fast-generate-001",
        "veo-3.0-generate-001",
        "veo-2.0-generate-001",
    ],
    "fal": [
        "fal-ai/flux-general",
        "fal-ai/flux-general/image-to-image",
        "fal-ai/flux-2/turbo",
        "fal-ai/flux-pro/v1.1",
        "fal-ai/kling-image/o1",
        "fal-ai/wan/v1/text-to-video",
        "fal-ai/wan/v2.1/text-to-video",
        "fal-ai/kling-video/v2.1/standard/text-to-video",
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
