"""Tests for AirByNature sensors."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.const import DOMAIN
from custom_components.airbynature.models import DeviceGroup

from .helpers import entity_id, setup_integration


@pytest.mark.parametrize(
    ("unique_id", "expected"),
    [
        ("100_avg_temperature", "25.9"),
        ("100_mode", "comfort"),
        ("100_current_rule", "Svale 1 - Fugt 1 (>55%)"),
        ("100_pause_inlets_until", STATE_UNKNOWN),
        ("100_status", "ok"),
        ("200_inlet_temperature", "23.89"),
        ("200_outlet_temperature", "25.9"),
        ("200_external_temperature", "24.97"),
        ("200_inlet_humidity", "60.3"),
        ("200_outlet_humidity", "55.3"),
        ("200_co2", "440.3"),
        ("200_tvoc", "46.9"),
        ("200_inlet_fan", "0"),
        ("200_outlet_fan", "74"),
        ("200_inlet_fan1_rpm", "0"),
        ("200_outlet_fan1_rpm", "3617"),
        ("200_last_measurement", "2024-09-24T16:00:28+00:00"),
        ("200_wifi_signal", "28"),
        ("200_inlet_speed_factor", "55.0"),
        ("200_outlet_speed_factor", "65.0"),
        ("200_interval", "60"),
    ],
)
async def test_sensor_values(
    hass: HomeAssistant, init_integration: MockConfigEntry, unique_id: str, expected: str
) -> None:
    state = hass.states.get(entity_id(hass, "sensor", unique_id))

    assert state is not None
    assert state.state == expected


async def test_sensor_units(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    def unit(unique_id: str) -> str | None:
        return hass.states.get(entity_id(hass, "sensor", unique_id)).attributes.get(
            "unit_of_measurement"
        )

    assert unit("100_avg_temperature") == "°C"
    assert unit("200_inlet_humidity") == "%"
    assert unit("200_co2") == "ppm"
    assert unit("200_tvoc") == "ppb"
    assert unit("200_outlet_fan1_rpm") == "rpm"
    assert unit("200_outlet_fan") == "%"
    assert unit("200_wifi_signal") is None


async def test_fan2_sensors_disabled_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    registry = er.async_get(hass)
    for key in ("200_inlet_fan2_rpm", "200_outlet_fan2_rpm", "100_pause_until"):
        entry = registry.async_get(entity_id(hass, "sensor", key))
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_diagnostic_category(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id(hass, "sensor", "200_wifi_signal"))
    assert entry.entity_category == "diagnostic"


async def test_device_tree(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    registry = dr.async_get(hass)
    group = registry.async_get_device(identifiers={(DOMAIN, "group_100")})
    unit = registry.async_get_device(identifiers={(DOMAIN, "unit_200")})

    assert unit is not None
    assert unit.name == "Loftanlæg"
    assert unit.model == "main-v2"
    assert unit.via_device_id == group.id

    sensor = er.async_get(hass).async_get(entity_id(hass, "sensor", "200_co2"))
    assert sensor.device_id == unit.id


async def test_multiple_groups(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    first = DeviceGroup.from_api(group_payload)
    group_payload["data"]["id"] = 101
    group_payload["data"]["address"] = "Andenvej 2"
    group_payload["data"]["devices"][0]["id"] = 201
    group_payload["data"]["devices"][0]["latest_history"]["outlet_co2"] = 999.0
    mock_client.async_get_groups.return_value = [first, DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == "440.3"
    assert hass.states.get(entity_id(hass, "sensor", "201_co2")).state == "999.0"
    unit = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "unit_201")})
    group = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "group_101")})
    assert group.name == "Andenvej 2"
    assert unit.via_device_id == group.id


async def test_offline_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"][0]["is_online"] = False
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_id(hass, "sensor", "200_wifi_signal")).state == "28"
    assert hass.states.get(entity_id(hass, "sensor", "100_avg_temperature")).state == "25.9"


async def test_unit_without_history(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"][0]["latest_history"] = None
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == STATE_UNKNOWN
    assert (
        hass.states.get(entity_id(hass, "sensor", "200_last_measurement")).state
        == STATE_UNKNOWN
    )


async def test_unknown_mode_is_shown_verbatim(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["mode"] = "away"
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "sensor", "100_mode")).state == "away"


async def test_values_follow_updates(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"][0]["latest_history"]["outlet_co2"] = 612.5
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == "612.5"


async def test_removed_unit_becomes_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"] = []
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_id(hass, "sensor", "100_avg_temperature")).state == "25.9"
