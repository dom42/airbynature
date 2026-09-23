"""Tests for AirByNature number entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.api import ApiError
from custom_components.airbynature.const import DOMAIN
from custom_components.airbynature.models import DeviceGroup
from custom_components.airbynature.number import remaining_hours

from .helpers import entity_id, setup_integration

NOW = datetime(2024, 9, 24, 16, 0, tzinfo=UTC)


async def _set_value(hass: HomeAssistant, entity: str, value: float) -> None:
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity, ATTR_VALUE: value},
        blocking=True,
    )


@pytest.mark.parametrize(
    ("until", "expected"),
    [
        (None, 0),
        (NOW - timedelta(minutes=1), 0),
        (NOW, 0),
        (NOW + timedelta(minutes=1), 1),
        (NOW + timedelta(minutes=90), 2),
        (NOW + timedelta(hours=30), 30),
    ],
)
def test_remaining_hours(until: datetime | None, expected: int) -> None:
    assert remaining_hours(until, NOW) == expected


async def test_target_temperature_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(entity_id(hass, "number", "100_target_temperature"))

    assert float(state.state) == 23
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 40
    assert state.attributes["step"] == 1
    assert state.attributes["unit_of_measurement"] == "°C"


async def test_set_target_temperature(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["target_temperature"] = 21
    mock_client.async_set_target_temperature.return_value = DeviceGroup.from_api(
        group_payload
    )
    entity = entity_id(hass, "number", "100_target_temperature")

    await _set_value(hass, entity, 21)

    mock_client.async_set_target_temperature.assert_awaited_once_with(100, 21)
    assert float(hass.states.get(entity).state) == 21
    # Updated from the PUT response, not from an extra poll.
    assert mock_client.async_get_groups.await_count == 1


async def test_pause_inlets_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    until = dt_util.utcnow() + timedelta(minutes=90)
    group_payload["data"]["pause_inlets_until"] = until.isoformat()
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id(hass, "number", "100_pause_inlets"))
    assert float(state.state) == 2
    assert state.attributes["max"] == 24


async def test_pause_longer_than_max(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    until = dt_util.utcnow() + timedelta(hours=30)
    group_payload["data"]["pause_inlets_until"] = until.isoformat()
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id(hass, "number", "100_pause_inlets"))
    assert float(state.state) == 30


async def test_not_paused_shows_zero(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(entity_id(hass, "number", "100_pause_inlets"))

    assert float(state.state) == 0


async def test_set_pause_inlets(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    entity = entity_id(hass, "number", "100_pause_inlets")

    with patch("custom_components.airbynature.number._utcnow", return_value=NOW):
        await _set_value(hass, entity, 2)

    mock_client.async_set_pause_inlets.assert_awaited_once_with(
        100, NOW + timedelta(hours=2)
    )


async def test_stop_pause_inlets(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    entity = entity_id(hass, "number", "100_pause_inlets")

    await _set_value(hass, entity, 0)

    mock_client.async_set_pause_inlets.assert_awaited_once_with(100, None)


async def test_command_failure_raises(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_set_target_temperature.side_effect = ApiError("HTTP 500")
    entity = entity_id(hass, "number", "100_target_temperature")

    with pytest.raises(HomeAssistantError):
        await _set_value(hass, entity, 20)


async def test_controls_hidden_without_permission(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["meta"]["permissions"]["canChangeTemperature"] = False
    group_payload["meta"]["permissions"]["canPauseInlets"] = False
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("number", DOMAIN, "100_target_temperature") is None
    assert registry.async_get_entity_id("number", DOMAIN, "100_pause_inlets") is None
