# ABOUTME: Pricing lookup for cost estimates across all backends.
# ABOUTME: Priority chain: project.yaml override > FAL API > static defaults (Google, Replicate) > None.

import json
import logging
import os
import urllib.request

from storyboard_gen.models import Scene

logger = logging.getLogger(__name__)

# Session cache: endpoint_id -> pricing dict (or None for failed lookups)
_price_cache: dict[str, dict | None] = {}

# FAL-billed model prefixes (models routed through FAL's billing)
_FAL_PREFIXES = ("fal-ai/", "xai/", "wan/")

# Standard Flux output is ~1 megapixel (e.g. 1024x1024, 1344x768).
_MEGAPIXELS_PER_IMAGE = 1.0

# Static pricing defaults for models without a live pricing API.
# Google pricing as of 2026-03 (Gemini API pricing page).
# Replicate pricing as of 2026-03 (replicate.com/pricing).
_STATIC_PRICES: dict[str, dict] = {
    # --- Google Imagen (stills) ---
    "imagen-4.0-fast-generate-001": {
        "unit_price": 0.02,
        "unit": "image",
        "currency": "USD",
    },
    "imagen-4.0-generate-001": {
        "unit_price": 0.04,
        "unit": "image",
        "currency": "USD",
    },
    "imagen-4.0-ultra-generate-001": {
        "unit_price": 0.06,
        "unit": "image",
        "currency": "USD",
    },
    # --- Google Veo (clips) ---
    "veo-2.0-generate-001": {
        "unit_price": 0.35,
        "unit": "second",
        "currency": "USD",
    },
    "veo-3.0-fast-generate-001": {
        "unit_price": 0.15,
        "unit": "second",
        "currency": "USD",
    },
    "veo-3.0-generate-001": {
        "unit_price": 0.40,
        "unit": "second",
        "currency": "USD",
    },
    "veo-3.1-fast-generate-001": {
        "unit_price": 0.15,
        "unit": "second",
        "currency": "USD",
    },
    "veo-3.1-generate-001": {
        "unit_price": 0.40,
        "unit": "second",
        "currency": "USD",
    },
    # --- Replicate (stills only) ---
    "black-forest-labs/flux-1.1-pro": {
        "unit_price": 0.04,
        "unit": "image",
        "currency": "USD",
    },
    "black-forest-labs/flux-dev": {
        "unit_price": 0.025,
        "unit": "image",
        "currency": "USD",
    },
}


def _normalise_unit(unit: str) -> str | None:
    """Normalise FAL API unit strings to canonical forms.

    The FAL pricing API returns varying unit names across models.
    We normalise to "image" (flat per-generation), "second"
    (duration-based), or "megapixel" (per-megapixel, estimated
    at ~1MP per image for standard Flux outputs).

    Units we cannot reliably convert (compute seconds) return
    None — the caller should treat these as unavailable.

    Args:
        unit: Raw unit string from the API.

    Returns:
        Normalised unit: "image", "second", "megapixel",
        None for unsupported units, or the original string
        for unknown units.
    """
    lower = unit.lower()
    if lower in ("image", "images"):
        return "image"
    if lower in ("second", "seconds"):
        return "second"
    if lower in ("megapixel", "megapixels"):
        return "megapixel"
    # Compute seconds are not video seconds — unsuitable for cost estimation.
    if lower == "compute seconds":
        return None
    return unit


def _fetch_fal_price(model: str) -> dict | None:
    """Fetch pricing from the FAL live API (internal helper).

    Args:
        model: The model endpoint ID.

    Returns:
        Pricing dict or None if unavailable.
    """
    if not any(model.startswith(prefix) for prefix in _FAL_PREFIXES):
        return None

    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        return None

    # Check session cache
    if model in _price_cache:
        return _price_cache[model]

    url = f"https://api.fal.ai/v1/models/pricing?endpoint_id={model}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Key {fal_key}")

    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310 — trusted FAL API
            data = json.loads(resp.read())

        prices = data.get("prices", [])
        if not prices:
            result = None
        else:
            entry = prices[0]
            normalised = _normalise_unit(entry["unit"])
            if normalised is None:
                logger.debug(
                    "Unsupported pricing unit %r for %s — treating as unavailable",
                    entry["unit"],
                    model,
                )
                result = None
            else:
                result = {
                    "unit_price": entry["unit_price"],
                    "unit": normalised,
                    "currency": entry["currency"],
                }
    except (OSError, KeyError, json.JSONDecodeError, IndexError) as exc:
        logger.debug("Failed to fetch pricing for %s: %s", model, exc)
        result = None

    _price_cache[model] = result
    return result


def fetch_price(model: str, *, pricing_override: dict | None = None) -> dict | None:
    """Look up pricing for any model using the priority chain.

    Priority: project.yaml override > FAL live API > static defaults > None.

    Args:
        model: The model endpoint ID (e.g. "fal-ai/flux-general",
            "imagen-4.0-generate-001", "veo-3.1-fast-generate-001").
        pricing_override: Optional pricing dict from project.yaml provider
            config. When present, returned directly without any API call.

    Returns:
        Dict with keys ``unit_price`` (float), ``unit`` (str), ``currency``
        (str), or None if pricing is unavailable.
    """
    # 1. Project-level override wins
    if pricing_override is not None:
        return pricing_override

    # 2. FAL live API for FAL-billed models
    fal_result = _fetch_fal_price(model)
    if fal_result is not None:
        return fal_result

    # 3. Static defaults (Google, Replicate)
    if model in _STATIC_PRICES:
        return _STATIC_PRICES[model]

    return None


# Backward-compatible alias for callers not yet migrated
fetch_fal_price = fetch_price


def estimate_scene_cost(scene: Scene, pricing: dict | None) -> float | None:
    """Estimate the cost to generate a scene.

    Args:
        scene: The scene to estimate.
        pricing: Pricing dict from ``fetch_price``, or None.

    Returns:
        Estimated cost in the pricing currency, or None if unavailable.
    """
    if pricing is None:
        return None

    unit_price = pricing["unit_price"]
    unit = pricing["unit"]

    if unit == "second":
        return unit_price * scene.duration
    # Megapixel: ~1MP per image for standard Flux outputs
    if unit == "megapixel":
        return unit_price * _MEGAPIXELS_PER_IMAGE
    # Flat per-image cost
    return unit_price


def format_cost_line(scene: Scene, pricing: dict | None) -> str:
    """Format a human-readable cost estimate line for a scene.

    Args:
        scene: The scene to format.
        pricing: Pricing dict from ``fetch_price``, or None.

    Returns:
        A string like ``$0.04/image`` or ``$0.40 (8s x $0.05/s)``
        or ``Estimated cost: unavailable``.
    """
    if pricing is None:
        return "Estimated cost: unavailable"

    unit_price = pricing["unit_price"]
    unit = pricing["unit"]
    cost = estimate_scene_cost(scene, pricing)

    if unit == "second":
        return f"Estimated cost: ${cost:.2f} ({scene.duration:g}s \u00d7 ${unit_price:.2f}/s)"
    if unit == "megapixel":
        return f"Estimated cost: ${cost:.2f}/image (~1MP)"
    return f"Estimated cost: ${cost:.2f}/image"
