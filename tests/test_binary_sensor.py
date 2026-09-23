"""Tests for AirByNature binary sensors."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.models import DeviceGroup

from .helpers import entity_id, setup_integration


@pytest.mark.parametrize(
    ("unique_id", "expected"),
    [
        ("100_rule_enabled", STATE_ON),
        ("100_drying", STATE_OFF),
        ("200_online", STATE_ON),
        ("200_filter", STATE_ON),
        ("200_drying_heat_exchanger", STATE_OFF),
    ],
)
async def test_binary_sensor_values(
    hass: HomeAssistant, init_integration: MockConfigEntry, unique_id: str, expected: str
) -> None:
    state = hass.states.get(entity_id(hass, "binary_sensor", unique_id))

    assert state is not None
    assert state.state == expected


async def test_online_device_class(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(entity_id(hass, "binary_sensor", "200_online"))

    assert state.attributes["device_class"] == "connectivity"


async def test_offline_unit_reports_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"][0]["is_online"] = False
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "binary_sensor", "200_online")).state == STATE_OFF
