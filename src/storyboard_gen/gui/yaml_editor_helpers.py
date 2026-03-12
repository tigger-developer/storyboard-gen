# ABOUTME: Format-preserving YAML read/write helpers for the project settings form.
# ABOUTME: Uses ruamel.yaml to maintain comments, ordering, and formatting.

from __future__ import annotations

import logging
from pathlib import Path

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)


def load_yaml_roundtrip(path: Path) -> dict:
    """Load a YAML file preserving comments and formatting.

    Args:
        path: Path to the YAML file.

    Returns:
        A ruamel.yaml CommentedMap (dict-like, preserves formatting).
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    with open(path, encoding="utf-8") as f:
        return yaml.load(f)


def save_yaml_roundtrip(data: dict, path: Path) -> None:
    """Save a ruamel.yaml structure back to disk, preserving formatting.

    Args:
        data: The CommentedMap data to save.
        path: Target file path.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)


def update_nested(data: dict, key_path: list[str], value: object) -> None:
    """Set a nested value in a ruamel.yaml CommentedMap.

    Creates intermediate dicts if needed. Removes the key if value is None.

    Args:
        data: The root CommentedMap.
        key_path: List of keys like ["providers", "still", "backend"].
        value: The value to set, or None to remove.
    """
    target = data
    for key in key_path[:-1]:
        if key not in target:
            target[key] = {}
        target = target[key]

    final_key = key_path[-1]
    if value is None:
        target.pop(final_key, None)
    else:
        target[final_key] = value


def get_nested(data: dict, key_path: list[str], default: object = None) -> object:
    """Get a nested value from a dict safely.

    Args:
        data: The root dict.
        key_path: List of keys to traverse.
        default: Value to return if path doesn't exist.

    Returns:
        The value at the key path, or default.
    """
    target = data
    for key in key_path:
        if not isinstance(target, dict) or key not in target:
            return default
        target = target[key]
    return target
