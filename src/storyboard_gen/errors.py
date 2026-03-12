# ABOUTME: Error message extraction utilities for API responses.
# ABOUTME: Converts raw API error dicts/lists/strings into clean, human-readable messages.

from __future__ import annotations

_FALLBACK = "Unknown error (no details available)"


def clean_api_error(raw: object) -> str:
    """Extract a human-readable message from a raw API error.

    Handles common patterns from Google, FAL, and Replicate APIs:
    - ``{"message": "..."}`` — direct message field
    - ``{"error": {"message": "..."}}`` — nested error object
    - ``{"detail": "..."}`` — FastAPI/Pydantic-style detail
    - ``[{"msg": "..."}]`` — list of validation errors
    - Plain strings — returned as-is (with prompt echo trimmed)

    Args:
        raw: The raw error value (dict, list, str, or other).

    Returns:
        A clean, single-line-ish error message for user display.
    """
    if raw is None:
        return _FALLBACK

    if isinstance(raw, str):
        if not raw.strip():
            return _FALLBACK
        return _clean_string(raw)

    if isinstance(raw, dict):
        return _clean_dict(raw)

    if isinstance(raw, list):
        return _clean_list(raw)

    return str(raw) or _FALLBACK


def _clean_string(text: str) -> str:
    """Trim prompt echoes and clean up error strings."""
    # FAL sometimes echoes the prompt after the error
    for marker in ("prompt was:", "arguments="):
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx].rstrip(", ")
    return text.strip()


def _clean_dict(data: dict) -> str:
    """Extract message from a dict-shaped error."""
    # Direct message field (Google, generic)
    if "message" in data and isinstance(data["message"], str):
        return data["message"]

    # Nested error object (Google REST, OpenAI-style)
    if "error" in data and isinstance(data["error"], dict):
        inner = data["error"]
        if "message" in inner and isinstance(inner["message"], str):
            return inner["message"]

    # FastAPI/Pydantic detail (FAL)
    if "detail" in data:
        detail = data["detail"]
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            return _clean_list(detail)

    # No known key — stringify
    return str(data) if data else _FALLBACK


def _clean_list(items: list) -> str:
    """Join messages from a list of error objects or strings."""
    if not items:
        return _FALLBACK

    messages = []
    for item in items:
        if isinstance(item, dict):
            msg = item.get("msg") or item.get("message") or str(item)
            messages.append(str(msg))
        elif isinstance(item, str):
            messages.append(item)
        else:
            messages.append(str(item))

    return "; ".join(messages)
