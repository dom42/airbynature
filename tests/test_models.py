"""Tests for AirByNature model parsing."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from custom_components.airbynature.models import DeviceGroup


def test_parse_group(group_payload: dict[str, Any]) -> None:
    group = DeviceGroup.from_api(group_payload)

    assert group.id == 100
    assert group.name == "Test User"
    assert group.display_name == "Testvej 1"
    assert group.target_temperature == 23
    assert group.avg_temp == 25.9
    assert group.mode == "comfort"
    assert group.current_running_rule == "Svale 1 - Fugt 1 (>55%)"
    assert group.is_rule_enabled is True
    assert group.is_drying is False
    assert group.status == "ok"
    assert group.pause_until is None
    assert group.pause_inlets_until is None
    assert group.permissions.can_change_temperature is True
    assert group.permissions.can_change_mode is False
    assert group.permissions.can_change_comfort_level is True
    assert group.permissions.can_pause_inlets is True


def test_parse_unit(group_payload: dict[str, Any]) -> None:
    unit = DeviceGroup.from_api(group_payload).units[200]

    assert unit.name == "Loftanlæg"
    assert unit.type == "main-v2"
    assert unit.comfort_level == 3
    assert unit.is_online is True
    assert unit.wifi_signal == 28
    assert unit.inlet_speed_factor == 55.0
    assert unit.outlet_speed_factor == 65.0
    assert unit.has_filter is True
    assert unit.is_drying_heat_exchanger is False
    assert unit.current_interval == 60
    assert unit.serial_number is None
    m = unit.measurements
    assert m.inlet_temp == 23.89
    assert m.inlet_humid == 60.3
    assert m.inlet_fan == 0
    assert m.outlet_temp == 25.9
    assert m.outlet_humid == 55.3
    assert m.outlet_co2 == 440.3
    assert m.outlet_fan == 74
    assert m.outlet_tvoc == 46.9
    assert m.outlet_fan1_rpm == 3617
    assert m.outlet_fan2_rpm == 0
    assert m.external_temp == 24.97
    assert m.measured_at == datetime(2024, 9, 24, 16, 0, 28, tzinfo=UTC)


def test_parse_pause_timestamp(group_payload: dict[str, Any]) -> None:
    group_payload["data"]["pause_inlets_until"] = "2024-09-24T16:59:33.000000Z"

    group = DeviceGroup.from_api(group_payload)

    assert group.pause_inlets_until == datetime(2024, 9, 24, 16, 59, 33, tzinfo=UTC)


@pytest.mark.parametrize("history", [None, "missing"])
def test_missing_latest_history(group_payload: dict[str, Any], history: Any) -> None:
    device = group_payload["data"]["devices"][0]
    if history == "missing":
        del device["latest_history"]
    else:
        device["latest_history"] = history

    m = DeviceGroup.from_api(group_payload).units[200].measurements

    assert m.inlet_temp is None
    assert m.outlet_co2 is None
    assert m.measured_at is None


@pytest.mark.parametrize("value", ["", "n/a", None])
def test_invalid_numbers_become_none(group_payload: dict[str, Any], value: Any) -> None:
    group_payload["data"]["avg_temp"] = value
    group_payload["data"]["devices"][0]["outlet_speed_factor"] = value

    group = DeviceGroup.from_api(group_payload)

    assert group.avg_temp is None
    assert group.units[200].outlet_speed_factor is None


@pytest.mark.parametrize("address", ["", None])
def test_display_name_falls_back_to_name(
    group_payload: dict[str, Any], address: str | None
) -> None:
    group_payload["data"]["address"] = address

    assert DeviceGroup.from_api(group_payload).display_name == "Test User"


def test_missing_meta_grants_no_permissions(group_payload: dict[str, Any]) -> None:
    del group_payload["meta"]

    permissions = DeviceGroup.from_api(group_payload).permissions

    assert permissions.can_change_temperature is False
    assert permissions.can_change_comfort_level is False
    assert permissions.can_pause_inlets is False


def test_group_without_devices(group_payload: dict[str, Any]) -> None:
    group_payload["data"]["devices"] = []

    assert DeviceGroup.from_api(group_payload).units == {}
