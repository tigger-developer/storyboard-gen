# ABOUTME: Tests for storyboard_gen.pricing.
# ABOUTME: Validates pricing API, static defaults, overrides, and cost estimation.

import json
from unittest.mock import patch

import pytest

from storyboard_gen.models import Scene
from storyboard_gen.pricing import (
    _STATIC_PRICES,
    _normalise_unit,
    estimate_scene_cost,
    fetch_price,
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

    def test_normalise_megapixels_returns_megapixel(self):
        """Megapixel pricing normalises to 'megapixel' for ~1MP estimation."""
        assert _normalise_unit("megapixels") == "megapixel"

    def test_normalise_megapixel_singular_returns_megapixel(self):
        """Singular 'megapixel' also normalises."""
        assert _normalise_unit("megapixel") == "megapixel"

    def test_normalise_seconds_to_second(self):
        assert _normalise_unit("seconds") == "second"

    def test_normalise_second_unchanged(self):
        assert _normalise_unit("second") == "second"

    def test_normalise_compute_seconds_returns_none(self):
        """Compute seconds ≠ video seconds; cannot estimate duration cost."""
        assert _normalise_unit("compute seconds") is None

    def test_normalise_units_returns_none(self):
        """'units' pricing unit treated as unavailable (#121 AC4)."""
        assert _normalise_unit("units") is None

    def test_normalise_unknown_returns_as_is(self):
        assert _normalise_unit("tokens") == "tokens"


# ---------------------------------------------------------------------------
# Unit tests: _STATIC_PRICES
# ---------------------------------------------------------------------------


class TestStaticPrices:
    """Tests for built-in static pricing defaults."""

    def test_imagen4_standard_in_static_prices(self):
        assert "imagen-4.0-generate-001" in _STATIC_PRICES
        p = _STATIC_PRICES["imagen-4.0-generate-001"]
        assert p["unit_price"] == 0.04
        assert p["unit"] == "image"

    def test_imagen4_fast_in_static_prices(self):
        assert "imagen-4.0-fast-generate-001" in _STATIC_PRICES
        assert _STATIC_PRICES["imagen-4.0-fast-generate-001"]["unit_price"] == 0.02

    def test_imagen4_ultra_in_static_prices(self):
        assert "imagen-4.0-ultra-generate-001" in _STATIC_PRICES
        assert _STATIC_PRICES["imagen-4.0-ultra-generate-001"]["unit_price"] == 0.06

    def test_veo31_fast_in_static_prices(self):
        assert "veo-3.1-fast-generate-001" in _STATIC_PRICES
        p = _STATIC_PRICES["veo-3.1-fast-generate-001"]
        assert p["unit_price"] == 0.15
        assert p["unit"] == "second"

    def test_veo31_standard_in_static_prices(self):
        assert "veo-3.1-generate-001" in _STATIC_PRICES
        assert _STATIC_PRICES["veo-3.1-generate-001"]["unit_price"] == 0.40

    def test_veo3_fast_in_static_prices(self):
        assert "veo-3.0-fast-generate-001" in _STATIC_PRICES
        assert _STATIC_PRICES["veo-3.0-fast-generate-001"]["unit_price"] == 0.15

    def test_veo3_standard_in_static_prices(self):
        assert "veo-3.0-generate-001" in _STATIC_PRICES
        assert _STATIC_PRICES["veo-3.0-generate-001"]["unit_price"] == 0.40

    def test_veo2_in_static_prices(self):
        assert "veo-2.0-generate-001" in _STATIC_PRICES
        assert _STATIC_PRICES["veo-2.0-generate-001"]["unit_price"] == 0.35

    def test_replicate_flux_pro_in_static_prices(self):
        assert "black-forest-labs/flux-1.1-pro" in _STATIC_PRICES
        p = _STATIC_PRICES["black-forest-labs/flux-1.1-pro"]
        assert p["unit_price"] == 0.04
        assert p["unit"] == "image"

    def test_replicate_flux_dev_in_static_prices(self):
        assert "black-forest-labs/flux-dev" in _STATIC_PRICES
        p = _STATIC_PRICES["black-forest-labs/flux-dev"]
        assert p["unit_price"] == 0.025
        assert p["unit"] == "image"


# ---------------------------------------------------------------------------
# Unit tests: fetch_price
# ---------------------------------------------------------------------------


class TestFetchPrice:
    """Tests for pricing lookup with priority: override > FAL API > static."""

    def _mock_response(self, data: dict, status: int = 200):
        """Create a mock urllib response."""
        from unittest.mock import MagicMock

        resp = MagicMock()
        resp.read.return_value = json.dumps(data).encode()
        resp.status = status
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *a: None
        return resp

    # --- Override priority ---

    def test_override_takes_priority_over_fal_api(self, monkeypatch):
        """project.yaml pricing override wins over FAL API."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        override = {"unit_price": 0.99, "unit": "image", "currency": "USD"}

        # Act — should not make any HTTP call
        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            result = fetch_price("fal-ai/flux-general", pricing_override=override)

        # Assert
        mock_urlopen.assert_not_called()
        assert result["unit_price"] == 0.99

    def test_override_takes_priority_over_static(self):
        """project.yaml pricing override wins over static defaults."""
        # Arrange
        override = {"unit_price": 0.99, "unit": "second", "currency": "USD"}

        # Act
        result = fetch_price("veo-3.1-fast-generate-001", pricing_override=override)

        # Assert — override, not $0.15 static default
        assert result["unit_price"] == 0.99

    # --- FAL API ---

    def test_fal_api_returns_pricing_dict(self, monkeypatch):
        """FAL API lookup returns normalised pricing dict."""
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
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)

            # Act
            result = fetch_price("fal-ai/flux-general")

        # Assert
        assert result is not None
        assert result["unit_price"] == 0.04
        assert result["unit"] == "image"

    def test_fal_api_caches_results(self, monkeypatch):
        """Second call for same model uses cached result."""
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
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)
            result1 = fetch_price("fal-ai/flux-general")
            result2 = fetch_price("fal-ai/flux-general")

        assert mock_urlopen.call_count == 1
        assert result1 == result2

    def test_fal_api_sends_auth_header(self, monkeypatch):
        """Authorization header includes FAL_KEY."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "my-secret-key")
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
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)
            fetch_price("fal-ai/flux-general")

        request = mock_urlopen.call_args[0][0]
        assert request.get_header("Authorization") == "Key my-secret-key"

    def test_fal_api_uses_correct_url(self, monkeypatch):
        """URL uses api.fal.ai."""
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
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)
            fetch_price("fal-ai/flux-general")

        request = mock_urlopen.call_args[0][0]
        assert "api.fal.ai" in request.full_url

    def test_fal_api_accepts_xai_model(self, monkeypatch):
        """xAI models are accepted by the FAL API path."""
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
            result = fetch_price("xai/grok-imagine-image")

        assert result is not None
        assert result["unit_price"] == 0.02

    def test_fal_api_accepts_wan_model(self, monkeypatch):
        """Wan 2.6 models are accepted by the FAL API path."""
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
            result = fetch_price("wan/v2.6/text-to-video")

        assert result is not None
        assert result["unit"] == "second"

    def test_fal_api_returns_none_without_key(self, monkeypatch):
        """FAL API returns None when FAL_KEY is not set, but static fallback used."""
        # Arrange
        monkeypatch.delenv("FAL_KEY", raising=False)
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()

        # Act — FAL model with no key: no API call, no static default
        result = fetch_price("fal-ai/flux-general")

        # Assert
        assert result is None

    def test_fal_api_megapixel_unit_returns_pricing(self, monkeypatch):
        """FAL API returning megapixel pricing is normalised to megapixel unit."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        response_data = {
            "prices": [
                {
                    "endpoint_id": "fal-ai/flux-2/turbo",
                    "unit_price": 0.008,
                    "unit": "megapixels",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)
            result = fetch_price("fal-ai/flux-2/turbo")

        # Assert
        assert result is not None
        assert result["unit_price"] == 0.008
        assert result["unit"] == "megapixel"
        assert result["currency"] == "USD"

    def test_fal_api_compute_seconds_unit_returns_none(self, monkeypatch):
        """FAL API returning compute-second pricing is treated as unavailable."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()
        response_data = {
            "prices": [
                {
                    "endpoint_id": "fal-ai/wan/v1/text-to-video",
                    "unit_price": 0.00017,
                    "unit": "compute seconds",
                    "currency": "USD",
                }
            ],
        }

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response(response_data)
            result = fetch_price("fal-ai/wan/v1/text-to-video")

        assert result is None

    def test_fal_api_network_error_returns_none(self, monkeypatch):
        """FAL API network error falls through to None for unknown models."""
        # Arrange
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()

        with patch("storyboard_gen.pricing.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = OSError("Connection refused")
            result = fetch_price("fal-ai/flux-general")

        assert result is None

    # --- Static defaults ---

    def test_static_default_for_google_still(self):
        """Google Imagen model returns static pricing without any API call."""
        # Act — no FAL_KEY needed
        result = fetch_price("imagen-4.0-generate-001")

        # Assert
        assert result is not None
        assert result["unit_price"] == 0.04
        assert result["unit"] == "image"

    def test_static_default_for_google_clip(self):
        """Google Veo model returns static pricing without any API call."""
        # Act
        result = fetch_price("veo-3.1-fast-generate-001")

        # Assert
        assert result is not None
        assert result["unit_price"] == 0.15
        assert result["unit"] == "second"

    def test_static_default_for_replicate_pro(self):
        """Replicate Flux Pro returns static pricing."""
        # Act
        result = fetch_price("black-forest-labs/flux-1.1-pro")

        # Assert
        assert result is not None
        assert result["unit_price"] == 0.04
        assert result["unit"] == "image"

    def test_static_default_for_replicate_dev(self):
        """Replicate Flux Dev returns static pricing."""
        # Act
        result = fetch_price("black-forest-labs/flux-dev")

        # Assert
        assert result is not None
        assert result["unit_price"] == 0.025
        assert result["unit"] == "image"

    def test_fal_api_failure_falls_back_to_static(self, monkeypatch):
        """When FAL API fails for a model that also has static pricing, static wins."""
        # Arrange — imagen-4.0-generate-001 is in both FAL namespace check
        # and static defaults, but FAL won't have it (no fal-ai/ prefix)
        monkeypatch.setenv("FAL_KEY", "test-key")
        from storyboard_gen.pricing import _price_cache

        _price_cache.clear()

        # Act — Google model: FAL API not called (no prefix), static default used
        result = fetch_price("imagen-4.0-generate-001")

        # Assert
        assert result is not None
        assert result["unit_price"] == 0.04


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

    def test_estimate_megapixel_scene_returns_flat_cost(self):
        """Megapixel pricing treated as ~1MP per image = unit_price."""
        # Arrange
        scene = Scene(
            number="1",
            title="Test",
            scene_type="still",
            prompt="test",
            duration=5,
        )
        pricing = {"unit_price": 0.008, "unit": "megapixel", "currency": "USD"}

        # Act
        cost = estimate_scene_cost(scene, pricing)

        # Assert
        assert cost == 0.008

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

    def test_format_cost_line_megapixel(self):
        """Megapixel scene shows approximate cost indicator."""
        # Arrange
        scene = Scene(
            number="1",
            title="Test",
            scene_type="still",
            prompt="test",
            duration=5,
        )
        pricing = {"unit_price": 0.008, "unit": "megapixel", "currency": "USD"}

        # Act
        line = format_cost_line(scene, pricing)

        # Assert
        assert "$0.01" in line
        assert "~1MP" in line

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
