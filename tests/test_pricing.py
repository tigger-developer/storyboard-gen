# ABOUTME: Tests for storyboard_gen.pricing.
# ABOUTME: Validates FAL pricing API integration, caching, and cost estimation.

import json
from unittest.mock import patch

import pytest

from storyboard_gen.models import Scene
from storyboard_gen.pricing import (
    _normalise_unit,
    estimate_scene_cost,
    fetch_fal_price,
    format_cost_line,
)


# ---------------------------------------------------------------------------
# Unit tests: _normalise_unit
# ---------------------------------------------------------------------------


class TestNormaliseUnit:
    """Tests for unit string normalisation."""

    def test_normalise_images_to_image(self):
        assert _normalise_unit("images") == "image"

    def test_normalise_image_unchanged(self):
        assert _normalise_unit("image") == "image"

    def test_normalise_megapixels_to_image(self):
        assert _normalise_unit("megapixels") == "image"

    def test_normalise_seconds_to_second(self):
        assert _normalise_unit("seconds") == "second"

    def test_normalise_second_unchanged(self):
        assert _normalise_unit("second") == "second"

    def test_normalise_compute_seconds_to_second(self):
        assert _normalise_unit("compute seconds") == "second"

    def test_normalise_unknown_returns_as_is(self):
        assert _normalise_unit("tokens") == "tokens"


# ---------------------------------------------------------------------------
# Unit tests: fetch_fal_price
# ---------------------------------------------------------------------------


class TestFetchFalPrice:
    """Tests for FAL pricing API lookup."""

    def _mock_response(self, data: dict, status: int = 200):
        """Create a mock urllib response."""
        from unittest.mock import MagicMock

        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode()
        resp.status = status
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *a: None
        return resp

    def test_fetch_fal_price_returns_pricing_dict(self, monkeypatch):
        """Successful lookup returns dict with unit_price, unit, currency."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        response_data = {
            "prices": [
                {
                    "endpoint_id": "fal-ai/flux-general",
                    "unit_price": 0.04,
                    "unit": "images",
                    "currency": "USD",
                }
            ],
            "next_cursor": None,
            "has_more": False,
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)

            # Act
            result = fetch_fal_price("fal-ai/flux-general")

        # Assert — unit normalised from "images" to "image"
        assert result is not None
        assert result["unit_price"] == 0.04
        assert result["unit"] == "image"
        assert result["currency"] == "USD"

    def test_fetch_fal_price_normalises_megapixels_to_image(self, monkeypatch):
        """Megapixels unit is normalised to image (flat per-image cost)."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        response_data = {
            "prices": [
                {
                    "endpoint_id": "fal-ai/flux-pro/v1.1",
                    "unit_price": 0.04,
                    "unit": "megapixels",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)

            # Act
            result = fetch_fal_price("fal-ai/flux-pro/v1.1")

        # Assert
        assert result["unit"] == "image"

    def test_fetch_fal_price_normalises_seconds(self, monkeypatch):
        """Seconds unit is normalised to second."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        response_data = {
            "prices": [
                {
                    "endpoint_id": "wan/v2.6/text-to-video",
                    "unit_price": 0.10,
                    "unit": "seconds",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)

            # Act
            result = fetch_fal_price("wan/v2.6/text-to-video")

        # Assert
        assert result["unit"] == "second"
        assert result["unit_price"] == 0.10

    def test_fetch_fal_price_normalises_compute_seconds(self, monkeypatch):
        """Compute seconds unit is normalised to second."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        response_data = {
            "prices": [
                {
                    "endpoint_id": "fal-ai/kling-video/v2.1/pro/text-to-video",
                    "unit_price": 0.00017,
                    "unit": "compute seconds",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)

            # Act
            result = fetch_fal_price("fal-ai/kling-video/v2.1/pro/text-to-video")

        # Assert
        assert result["unit"] == "second"

    def test_fetch_fal_price_returns_none_without_fal_key(self, monkeypatch):
        """Returns None when FAL_KEY is not set."""
        # Arrange
        monkeypatch.delenv("FAL_KEY", raising=False)

        # Act
        result = fetch_fal_price("fal-ai/flux-general")

        # Assert
        assert result is None

    def test_fetch_fal_price_returns_none_for_google_model(self, monkeypatch):
        """Returns None for Google models (no slash in ID)."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")

        # Act
        result = fetch_fal_price("imagen-4.0-generate-001")

        # Assert
        assert result is None

    def test_fetch_fal_price_returns_none_for_replicate_model(self, monkeypatch):
        """Returns None for Replicate models (different namespace)."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")

        # Act
        result = fetch_fal_price("black-forest-labs/flux-1.1-pro")

        # Assert
        assert result is None

    def test_fetch_fal_price_accepts_xai_model(self, monkeypatch):
        """xAI models (xai/*) are accepted and return pricing."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        response_data = {
            "prices": [
                {
                    "endpoint_id": "xai/grok-imagine-image",
                    "unit_price": 0.02,
                    "unit": "images",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)

            # Act
            result = fetch_fal_price("xai/grok-imagine-image")

        # Assert
        assert result is not None
        assert result["unit_price"] == 0.02

    def test_fetch_fal_price_accepts_wan_model(self, monkeypatch):
        """Wan 2.6 models (wan/*) are accepted and return pricing."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        response_data = {
            "prices": [
                {
                    "endpoint_id": "wan/v2.6/text-to-video",
                    "unit_price": 0.10,
                    "unit": "seconds",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)

            # Act
            result = fetch_fal_price("wan/v2.6/text-to-video")

        # Assert
        assert result is not None
        assert result["unit_price"] == 0.10

    def test_fetch_fal_price_returns_none_on_network_error(self, monkeypatch):
        """Returns None gracefully on network errors."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("Connection refused")

            # Act
            result = fetch_fal_price("fal-ai/flux-general")

        # Assert
        assert result is None

    def test_fetch_fal_price_returns_none_on_empty_prices(self, monkeypatch):
        """Returns None when the API returns an empty prices array."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        response_data = {"prices": [], "next_cursor": None, "has_more": False}

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)

            # Act
            result = fetch_fal_price("fal-ai/some-unknown-model")

        # Assert
        assert result is None

    def test_fetch_fal_price_caches_results(self, monkeypatch):
        """Second call for same model uses cached result, no HTTP call."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        response_data = {
            "prices": [
                {
                    "endpoint_id": "fal-ai/flux-general",
                    "unit_price": 0.04,
                    "unit": "images",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)

            # Act — two calls for same model
            from storyboard_gen.pricing import _price_cache

            _price_cache.clear()
            result1 = fetch_fal_price("fal-ai/flux-general")
            result2 = fetch_fal_price("fal-ai/flux-general")

        # Assert — only one HTTP call made
        assert mock_urlopen.call_count == 1
        assert result1 == result2

    def test_fetch_fal_price_sends_auth_header(self, monkeypatch):
        """Authorization header includes FAL_KEY."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "my-secret-key")
        response_data = {
            "prices": [
                {
                    "endpoint_id": "fal-ai/flux-general",
                    "unit_price": 0.04,
                    "unit": "images",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)
            from storyboard_gen.pricing import _price_cache

            _price_cache.clear()

            # Act
            fetch_fal_price("fal-ai/flux-general")

        # Assert — check the Request object passed to urlopen
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert request.get_header("Authorization") == "Key my-secret-key"

    def test_fetch_fal_price_uses_api_fal_ai_url(self, monkeypatch):
        """URL uses api.fal.ai (not rest.fal.ai)."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        response_data = {
            "prices": [
                {
                    "endpoint_id": "fal-ai/flux-general",
                    "unit_price": 0.04,
                    "unit": "images",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)
            from storyboard_gen.pricing import _price_cache

            _price_cache.clear()

            # Act
            fetch_fal_price("fal-ai/flux-general")

        # Assert
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert "api.fal.ai" in request.full_url
        assert "rest.fal.ai" not in request.full_url


# ---------------------------------------------------------------------------
# Unit tests: estimate_scene_cost
# ---------------------------------------------------------------------------


class TestEstimateSceneCost:
    """Tests for per-scene cost estimation."""

    def test_estimate_still_scene_returns_flat_cost(self):
        """Still scene cost = unit_price (flat per image)."""
        # Arrange
        scene = Scene(
            number="1",
            title="Test",
            scene_type="still",
            prompt="test",
            duration=5,
        )
        pricing = {"unit_price": 0.04, "unit": "image", "currency": "USD"}

        # Act
        cost = estimate_scene_cost(scene, pricing)

        # Assert
        assert cost == 0.04

    def test_estimate_clip_scene_returns_duration_cost(self):
        """Clip scene cost = unit_price * duration."""
        # Arrange
        scene = Scene(
            number="1",
            title="Test",
            scene_type="clip",
            prompt="test",
            duration=8,
        )
        pricing = {"unit_price": 0.05, "unit": "second", "currency": "USD"}

        # Act
        cost = estimate_scene_cost(scene, pricing)

        # Assert
        assert cost == pytest.approx(0.40)

    def test_estimate_scene_cost_returns_none_when_no_pricing(self):
        """Returns None when pricing is None."""
        # Arrange
        scene = Scene(
            number="1",
            title="Test",
            scene_type="still",
            prompt="test",
            duration=5,
        )

        # Act
        cost = estimate_scene_cost(scene, None)

        # Assert
        assert cost is None


# ---------------------------------------------------------------------------
# Unit tests: format_cost_line
# ---------------------------------------------------------------------------


class TestFormatCostLine:
    """Tests for cost line formatting."""

    def test_format_cost_line_still(self):
        """Still scene shows flat cost."""
        # Arrange
        scene = Scene(
            number="1",
            title="Test",
            scene_type="still",
            prompt="test",
            duration=5,
        )
        pricing = {"unit_price": 0.04, "unit": "image", "currency": "USD"}

        # Act
        line = format_cost_line(scene, pricing)

        # Assert
        assert "$0.04" in line
        assert "image" in line

    def test_format_cost_line_clip(self):
        """Clip scene shows calculation."""
        # Arrange
        scene = Scene(
            number="1",
            title="Test",
            scene_type="clip",
            prompt="test",
            duration=8,
        )
        pricing = {"unit_price": 0.05, "unit": "second", "currency": "USD"}

        # Act
        line = format_cost_line(scene, pricing)

        # Assert
        assert "$0.40" in line
        assert "8" in line
        assert "$0.05" in line

    def test_format_cost_line_returns_unavailable_when_no_pricing(self):
        """Returns 'unavailable' when pricing is None."""
        # Arrange
        scene = Scene(
            number="1",
            title="Test",
            scene_type="still",
            prompt="test",
            duration=5,
        )

        # Act
        line = format_cost_line(scene, None)

        # Assert
        assert "unavailable" in line.lower()
