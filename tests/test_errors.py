# ABOUTME: Tests for storyboard_gen.errors module.
# ABOUTME: Validates clean_api_error() extracts human-readable messages from API responses.

from storyboard_gen.errors import clean_api_error


class TestCleanApiError:
    """Tests for clean_api_error() message extraction."""

    def test_plain_string_returned_as_is(self):
        """Plain string input returned unchanged."""
        assert clean_api_error("Something went wrong") == "Something went wrong"

    def test_dict_with_message_key(self):
        """Dict with 'message' key extracts the message."""
        err = {"code": 3, "message": "Unsupported output video duration 4 seconds"}
        assert clean_api_error(err) == "Unsupported output video duration 4 seconds"

    def test_dict_with_error_message_key(self):
        """Dict with nested 'error.message' extracts the message."""
        err = {"error": {"message": "Quota exceeded", "code": 429}}
        assert clean_api_error(err) == "Quota exceeded"

    def test_dict_with_detail_key(self):
        """Dict with 'detail' key extracts the detail."""
        err = {"detail": "Invalid request parameters"}
        assert clean_api_error(err) == "Invalid request parameters"

    def test_list_of_dicts_with_msg_key(self):
        """List of validation errors extracts msg fields."""
        err = [
            {"type": "missing", "msg": "Field required", "loc": ["body", "image_urls"]},
            {"type": "value_error", "msg": "Invalid URL format"},
        ]
        result = clean_api_error(err)
        assert "Field required" in result
        assert "Invalid URL format" in result

    def test_list_of_strings(self):
        """List of plain strings joined together."""
        err = ["Error 1", "Error 2"]
        result = clean_api_error(err)
        assert "Error 1" in result
        assert "Error 2" in result

    def test_empty_string_returns_fallback(self):
        """Empty string returns generic fallback message."""
        assert "unknown" in clean_api_error("").lower()

    def test_none_returns_fallback(self):
        """None returns generic fallback message."""
        assert "unknown" in clean_api_error(None).lower()

    def test_empty_dict_returns_fallback(self):
        """Empty dict returns generic fallback message."""
        assert "unknown" in clean_api_error({}).lower()

    def test_empty_list_returns_fallback(self):
        """Empty list returns generic fallback message."""
        assert "unknown" in clean_api_error([]).lower()

    def test_nested_dict_stringified(self):
        """Dict without known keys stringifies cleanly."""
        err = {"foo": "bar", "baz": 42}
        result = clean_api_error(err)
        assert "foo" in result or "bar" in result

    def test_fal_exception_string_with_prompt_echo(self):
        """FAL error string containing prompt echo is truncated."""
        err = (
            "{'detail': [{'type': 'missing', 'msg': 'Field required'}]} "
            "prompt was: 'A beautiful sunset over the ocean with warm colours'"
        )
        result = clean_api_error(err)
        # Should contain the error part, not the echoed prompt
        assert "Field required" in result or "missing" in result

    def test_google_operation_error_dict(self):
        """Google operation.error dict format."""
        err = {"code": 3, "message": "Video generation failed: safety filter"}
        assert "Video generation failed: safety filter" in clean_api_error(err)
