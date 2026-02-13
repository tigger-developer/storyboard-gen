# ABOUTME: Provider registry and factory for storyboard-gen.
# ABOUTME: Lazily imports provider implementations to avoid requiring unused SDKs.

import logging

from storyboard_gen.providers.base import ImageProvider

logger = logging.getLogger(__name__)

PROVIDERS = {
    "google": "storyboard_gen.providers.google.GoogleProvider",
    "fal": "storyboard_gen.providers.fal.FalProvider",
    "replicate": "storyboard_gen.providers.replicate.ReplicateProvider",
}


def create_provider(
    backend: str, model: str, options: dict | None = None
) -> ImageProvider:
    """Create a provider instance by backend name.

    Uses lazy imports so unused provider SDKs are not required.

    Args:
        backend: Provider name ("google", "fal", or "replicate").
        model: Provider-specific model identifier.
        options: Provider-specific options dict.

    Returns:
        An ImageProvider instance.

    Raises:
        ValueError: If the backend is unknown.
        ImportError: If the provider's SDK is not installed.
    """
    qualified = PROVIDERS.get(backend)
    if not qualified:
        raise ValueError(
            f"Unknown provider backend '{backend}'. "
            f"Must be one of: {', '.join(sorted(PROVIDERS))}"
        )

    module_path, class_name = qualified.rsplit(".", 1)

    import importlib

    module = importlib.import_module(module_path)
    provider_class = getattr(module, class_name)

    return provider_class(model=model, options=options or {})


__all__ = ["ImageProvider", "create_provider"]
