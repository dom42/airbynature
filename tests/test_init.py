"""Tests for AirByNature setup and unload."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.api import CannotConnect
from custom_components.airbynature.const import DOMAIN

from .helpers import setup_integration


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_group_device_registered(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "group_100")})

    assert device is not None
    assert device.name == "Testvej 1"
    assert device.manufacturer == "AirByNature"
    assert device.model == "Device group"


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_get_groups.side_effect = CannotConnect("boom")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_account_without_groups(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_get_groups.return_value = []

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass), mock_config_entry.entry_id
    )
    assert devices == []
