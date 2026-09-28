"""Tests for AirByNature select entities."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.api import CannotConnect
from custom_components.airbynature.const import DOMAIN
from custom_components.airbynature.models import DeviceGroup

from .helpers import entity_id, setup_integration


async def _select(hass: HomeAssistant, entity: str, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity, ATTR_OPTION: option},
        blocking=True,
    )


async def test_comfort_level_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(entity_id(hass, "select", "200_comfort_level"))

    assert state.state == "normal"
    assert state.attributes["options"] == [
        "off",
        "very_quiet",
        "quiet",
        "normal",
        "high",
        "extra_high",
    ]


async def test_select_comfort_level(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    entity = entity_id(hass, "select", "200_comfort_level")

    await _select(hass, entity, "high")
    await hass.async_block_till_done()

    mock_client.async_set_comfort_level.assert_awaited_once_with(100, 200, 4)
    assert mock_client.async_get_groups.await_count == 2


async def test_select_off_sends_level_zero(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    await _select(hass, entity_id(hass, "select", "200_comfort_level"), "off")

    mock_client.async_set_comfort_level.assert_awaited_once_with(100, 200, 0)


@pytest.mark.parametrize("level", [None, -1, 6])
async def test_comfort_level_out_of_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
    level: int | None,
) -> None:
    group_payload["data"]["devices"][0]["comfort_level"] = level
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id(hass, "select", "200_comfort_level"))
    assert state.state == STATE_UNKNOWN


async def test_command_failure_raises(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_set_comfort_level.side_effect = CannotConnect("timeout")

    with pytest.raises(HomeAssistantError):
        await _select(hass, entity_id(hass, "select", "200_comfort_level"), "normal")


async def test_hidden_without_permission(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["meta"]["permissions"]["canChangeAirCirculationLevel"] = False
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert (
        er.async_get(hass).async_get_entity_id("select", DOMAIN, "200_comfort_level")
        is None
    )
