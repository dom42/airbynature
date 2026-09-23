"""Fixtures for AirByNature tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.const import DOMAIN
from custom_components.airbynature.models import DeviceGroup

from .helpers import load_json, setup_integration


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
def group_payload() -> dict[str, Any]:
    """Return a fresh copy of the group detail response."""
    return load_json("group.json")


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the test account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="user@example.com",
        unique_id="10",
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )


@pytest.fixture
def mock_client(group_payload: dict[str, Any]) -> Generator[MagicMock]:
    """Patch the API client used by the integration setup."""
    with patch(
        "custom_components.airbynature.AirByNatureClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]
        client.async_get_user_id.return_value = 10
        client.async_set_target_temperature.return_value = DeviceGroup.from_api(
            group_payload
        )
        client.async_set_pause_inlets.return_value = DeviceGroup.from_api(
            group_payload
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> MockConfigEntry:
    """Set up the integration with the mocked client."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config flow tests from setting up the integration."""
    with patch(
        "custom_components.airbynature.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
def mock_flow_client() -> Generator[MagicMock]:
    """Patch the API client used by the config flow."""
    with patch(
        "custom_components.airbynature.config_flow.AirByNatureClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.async_get_user_id.return_value = 10
        yield client
