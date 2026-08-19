"""Save/reload regression tests for the Soniox STT provider.

Complements test_soniox_stt_service_factory.py (which covers create-service):
here we prove a Soniox configuration validates on save and round-trips back
through the STTConfig discriminated union on load.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import TypeAdapter

from api.services.configuration.check_validity import UserConfigurationValidator
from api.services.configuration.registry import (
    STTConfig,
    ServiceProviders,
    SonioxSTTConfiguration,
)


def test_soniox_config_roundtrips_through_stt_discriminated_union():
    """A saved Soniox config dict loads back as SonioxSTTConfiguration."""
    adapter = TypeAdapter(STTConfig)

    loaded = adapter.validate_python(
        {
            "provider": "soniox",
            "api_key": "test-key",
            "model": "stt-rt-v5",
            "language": "bn",
        }
    )

    assert isinstance(loaded, SonioxSTTConfiguration)
    assert loaded.provider == ServiceProviders.SONIOX
    assert loaded.model == "stt-rt-v5"
    assert loaded.language == "bn"


def test_soniox_api_key_valid_is_accepted_on_save():
    response = MagicMock()
    response.raise_for_status.return_value = None

    with patch(
        "api.services.configuration.check_validity.httpx.get", return_value=response
    ) as mock_get:
        assert (
            UserConfigurationValidator()._check_soniox_api_key("soniox", "good-key")
            is True
        )

    kwargs = mock_get.call_args.kwargs
    assert mock_get.call_args.args[0] == "https://api.soniox.com/v1/models"
    assert kwargs["headers"]["Authorization"] == "Bearer good-key"


def test_soniox_invalid_api_key_is_rejected_on_save():
    request = httpx.Request("GET", "https://api.soniox.com/v1/models")
    response = httpx.Response(401, request=request)
    error = httpx.HTTPStatusError("unauthorized", request=request, response=response)
    bad_response = MagicMock()
    bad_response.raise_for_status.side_effect = error

    with patch(
        "api.services.configuration.check_validity.httpx.get",
        return_value=bad_response,
    ):
        with pytest.raises(ValueError, match="Invalid Soniox API key"):
            UserConfigurationValidator()._check_soniox_api_key("soniox", "bad-key")


def test_soniox_network_error_is_reported_on_save():
    with patch(
        "api.services.configuration.check_validity.httpx.get",
        side_effect=httpx.ConnectError("no route"),
    ):
        with pytest.raises(ValueError, match="Could not reach the Soniox API"):
            UserConfigurationValidator()._check_soniox_api_key("soniox", "any-key")
