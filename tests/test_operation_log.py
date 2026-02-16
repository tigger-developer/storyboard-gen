# ABOUTME: Tests for the per-project operation log.
# ABOUTME: Verifies JSONL log entries are written for Veo operations (#33).

import json

from storyboard_gen.operation_log import log_operation, read_operations


class TestLogOperation:
    """Tests for writing operation log entries."""

    def test_log_operation_creates_log_file(self, tmp_path):
        """First log entry should create logs/operations.jsonl."""
        # Act
        log_operation(
            project_dir=tmp_path,
            scene_number="1",
            scene_type="clip",
            provider="google",
            model="veo-3.1-fast-generate-001",
            operation_id="operations/abc123",
            status="submitted",
        )

        # Assert
        log_file = tmp_path / "logs" / "operations.jsonl"
        assert log_file.exists()

    def test_log_operation_writes_valid_jsonl(self, tmp_path):
        """Each entry should be a valid JSON line."""
        # Act
        log_operation(
            project_dir=tmp_path,
            scene_number="3",
            scene_type="clip",
            provider="google",
            model="veo-3.1-fast-generate-001",
            operation_id="operations/xyz789",
            status="submitted",
        )

        # Assert
        log_file = tmp_path / "logs" / "operations.jsonl"
        line = log_file.read_text().strip()
        entry = json.loads(line)
        assert entry["scene"] == "3"
        assert entry["type"] == "clip"
        assert entry["provider"] == "google"
        assert entry["model"] == "veo-3.1-fast-generate-001"
        assert entry["operation_id"] == "operations/xyz789"
        assert entry["status"] == "submitted"
        assert "ts" in entry

    def test_log_operation_appends_to_existing(self, tmp_path):
        """Multiple entries should be appended, not overwritten."""
        # Act
        log_operation(
            project_dir=tmp_path,
            scene_number="1",
            scene_type="clip",
            provider="google",
            model="veo-3.1-fast-generate-001",
            operation_id="operations/first",
            status="submitted",
        )
        log_operation(
            project_dir=tmp_path,
            scene_number="1",
            scene_type="clip",
            provider="google",
            model="veo-3.1-fast-generate-001",
            operation_id="operations/first",
            status="completed",
        )

        # Assert
        log_file = tmp_path / "logs" / "operations.jsonl"
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["status"] == "submitted"
        assert json.loads(lines[1])["status"] == "completed"

    def test_log_operation_timestamp_is_iso8601(self, tmp_path):
        """Timestamp should be ISO 8601 format."""
        # Act
        log_operation(
            project_dir=tmp_path,
            scene_number="1",
            scene_type="clip",
            provider="google",
            model="veo-3.1-fast-generate-001",
            operation_id="operations/abc",
            status="submitted",
        )

        # Assert
        log_file = tmp_path / "logs" / "operations.jsonl"
        entry = json.loads(log_file.read_text().strip())
        ts = entry["ts"]
        assert ts.endswith("Z") or "+" in ts
        assert "T" in ts


class TestReadOperations:
    """Tests for reading operation log entries."""

    def test_read_operations_returns_all_entries(self, tmp_path):
        """Should return all log entries as dicts."""
        # Arrange
        log_operation(
            project_dir=tmp_path,
            scene_number="1",
            scene_type="clip",
            provider="google",
            model="veo-3.1",
            operation_id="op/1",
            status="submitted",
        )
        log_operation(
            project_dir=tmp_path,
            scene_number="1",
            scene_type="clip",
            provider="google",
            model="veo-3.1",
            operation_id="op/1",
            status="completed",
        )

        # Act
        entries = read_operations(tmp_path)

        # Assert
        assert len(entries) == 2

    def test_read_operations_empty_when_no_log(self, tmp_path):
        """Should return empty list when no log file exists."""
        # Act
        entries = read_operations(tmp_path)

        # Assert
        assert entries == []
