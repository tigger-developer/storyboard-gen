# ABOUTME: FAL pricing API integration for cost estimates.
# ABOUTME: Session-cached lookups; used by CLI dry-run and GUI.

import json
import logging
import os
import urllib.request

from storyboard_gen.models import Scene

logger = logging.getLogger(__name__)

# Session cache: endpoint_id -> pricing dict (or None for failed lookups)
_price_cache: dict[str, dict | None] = {}


def fetch_fal_price(model: str) -> dict | None:
    """Fetch pricing for a FAL model endpoint.

    Calls the FAL pricing API and caches the result for the session.

    Args:
        model: The model endpoint ID (e.g. "fal-ai/flux-general").

    Returns:
        Dict with keys ``unit_price`` (float), ``unit`` (str), ``currency``
        (str), or None if pricing is unavailable (non-FAL model, no key,
        API error).
    """
    # Only FAL models have pricing via this API
    if not model.startswith("fal-ai/"):
        return None

    fal_key = os.environ.get("FAL_KEY")
    if not fal_key:
        return None

    # Check session cache
    if model in _price_cache:
        return _price_cache[model]

    url = f"https://rest.fal.ai/v1/models/pricing?endpoint_id={model}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Key {fal_key}")

    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310 — trusted FAL API
            data = json.loads(resp.read())
        result = {
            "unit_price": data["unit_price"],
            "unit": data["unit"],
            "currency": data["currency"],
        }
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        logger.debug("Failed to fetch pricing for %s: %s", model, exc)
        result = None

    _price_cache[model] = result
    return result


def estimate_scene_cost(scene: Scene, pricing: dict | None) -> float | None:
    """Estimate the cost to generate a scene.

    Args:
        scene: The scene to estimate.
        pricing: Pricing dict from ``fetch_fal_price``, or None.

    Returns:
        Estimated cost in the pricing currency, or None if unavailable.
    """
    if pricing is None:
        return None

    unit_price = pricing["unit_price"]
    unit = pricing["unit"]

    if unit == "second":
        return unit_price * scene.duration
    # Flat per-image cost
    return unit_price


def format_cost_line(scene: Scene, pricing: dict | None) -> str:
    """Format a human-readable cost estimate line for a scene.

    Args:
        scene: The scene to format.
        pricing: Pricing dict from ``fetch_fal_price``, or None.

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
    return f"Estimated cost: ${cost:.2f}/image"
