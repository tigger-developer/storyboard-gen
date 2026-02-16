# ABOUTME: Per-project operation log for crash recovery.
# ABOUTME: Writes JSONL entries for Veo operations so they can be resumed after failures.

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def log_operation(
    project_dir: Path,
    scene_number: str,
    scene_type: str,
    provider: str,
    model: str,
    operation_id: str,
    status: str,
) -> None:
    """Append an operation log entry to logs/operations.jsonl.

    Args:
        project_dir: Root directory of the storyboard project.
        scene_number: Scene number being generated.
        scene_type: "still" or "clip".
        provider: Provider backend name (e.g. "google").
        model: Model identifier.
        operation_id: Provider-specific operation ID for resumption.
        status: One of "submitted", "polling", "completed", "failed", "timed_out".
    """
    log_dir = project_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "operations.jsonl"

    entry = {
        "ts": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scene": scene_number,
        "type": scene_type,
        "provider": provider,
        "model": model,
        "operation_id": operation_id,
        "status": status,
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    logger.debug("Operation log: %s", entry)


def read_operations(project_dir: Path) -> list[dict]:
    """Read all operation log entries from logs/operations.jsonl.

    Args:
        project_dir: Root directory of the storyboard project.

    Returns:
        List of operation log entries as dicts, in chronological order.
        Empty list if no log file exists.
    """
    log_file = project_dir / "logs" / "operations.jsonl"
    if not log_file.exists():
        return []

    entries = []
    with open(log_file) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries
