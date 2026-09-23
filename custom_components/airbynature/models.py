"""Typed models for AirByNature API responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    return None if number is None else int(number)


def _bool(value: Any) -> bool | None:
    return None if value is None else bool(value)


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Permissions:
    """What the account may change on a device group."""

    can_change_temperature: bool
    can_change_mode: bool
    can_change_comfort_level: bool
    can_pause_inlets: bool

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> Permissions:
        data = data or {}
        return cls(
            can_change_temperature=bool(data.get("canChangeTemperature")),
            can_change_mode=bool(data.get("canChangeMode")),
            can_change_comfort_level=bool(data.get("canChangeAirCirculationLevel")),
            can_pause_inlets=bool(data.get("canPauseInlets")),
        )


@dataclass(frozen=True, slots=True)
class Measurements:
    """Latest measurements reported by a unit."""

    inlet_temp: float | None = None
    inlet_humid: float | None = None
    inlet_fan: int | None = None
    inlet_fan1_rpm: int | None = None
    inlet_fan2_rpm: int | None = None
    outlet_temp: float | None = None
    outlet_humid: float | None = None
    outlet_co2: float | None = None
    outlet_fan: int | None = None
    outlet_tvoc: float | None = None
    outlet_fan1_rpm: int | None = None
    outlet_fan2_rpm: int | None = None
    external_temp: float | None = None
    measured_at: datetime | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> Measurements:
        data = data or {}
        return cls(
            inlet_temp=_float(data.get("inlet_temp")),
            inlet_humid=_float(data.get("inlet_humid")),
            inlet_fan=_int(data.get("inlet_fan")),
            inlet_fan1_rpm=_int(data.get("inlet_fan1_rpm")),
            inlet_fan2_rpm=_int(data.get("inlet_fan2_rpm")),
            outlet_temp=_float(data.get("outlet_temp")),
            outlet_humid=_float(data.get("outlet_humid")),
            outlet_co2=_float(data.get("outlet_co2")),
            outlet_fan=_int(data.get("outlet_fan")),
            outlet_tvoc=_float(data.get("outlet_tvoc")),
            outlet_fan1_rpm=_int(data.get("outlet_fan1_rpm")),
            outlet_fan2_rpm=_int(data.get("outlet_fan2_rpm")),
            external_temp=_float(data.get("external_temp")),
            measured_at=_datetime(data.get("created_at")),
        )


@dataclass(frozen=True, slots=True)
class Unit:
    """A physical ventilation unit in a device group."""

    id: int
    name: str
    type: str | None
    comfort_level: int | None
    is_online: bool
    wifi_signal: int | None
    inlet_speed_factor: float | None
    outlet_speed_factor: float | None
    has_filter: bool | None
    is_drying_heat_exchanger: bool | None
    current_interval: int | None
    serial_number: str | None
    measurements: Measurements

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Unit:
        return cls(
            id=int(data["id"]),
            name=data.get("name") or "",
            type=data.get("type"),
            comfort_level=_int(data.get("comfort_level")),
            is_online=bool(data.get("is_online")),
            wifi_signal=_int(data.get("wifi_signal")),
            inlet_speed_factor=_float(data.get("inlet_speed_factor")),
            outlet_speed_factor=_float(data.get("outlet_speed_factor")),
            has_filter=_bool(data.get("has_filter")),
            is_drying_heat_exchanger=_bool(data.get("is_drying_heat_exchanger")),
            current_interval=_int(data.get("current_interval")),
            serial_number=data.get("serial_number"),
            measurements=Measurements.from_api(data.get("latest_history")),
        )


@dataclass(frozen=True, slots=True)
class DeviceGroup:
    """A device group (an address) with its units."""

    id: int
    name: str
    address: str | None
    target_temperature: float | None
    avg_temp: float | None
    mode: str | None
    current_running_rule: str | None
    is_rule_enabled: bool | None
    is_drying: bool | None
    status: str | None
    pause_until: datetime | None
    pause_inlets_until: datetime | None
    permissions: Permissions
    units: dict[int, Unit]

    @classmethod
    def from_api(cls, body: dict[str, Any]) -> DeviceGroup:
        """Parse a full group response (``data`` and ``meta``)."""
        data = body["data"]
        units = (Unit.from_api(device) for device in data.get("devices") or [])
        return cls(
            id=int(data["id"]),
            name=data.get("name") or "",
            address=data.get("address") or None,
            target_temperature=_float(data.get("target_temperature")),
            avg_temp=_float(data.get("avg_temp")),
            mode=data.get("mode"),
            current_running_rule=data.get("current_running_rule"),
            is_rule_enabled=_bool(data.get("is_rule_enabled")),
            is_drying=_bool(data.get("is_drying")),
            status=data.get("status"),
            pause_until=_datetime(data.get("pause_until")),
            pause_inlets_until=_datetime(data.get("pause_inlets_until")),
            permissions=Permissions.from_api(
                (body.get("meta") or {}).get("permissions")
            ),
            units={unit.id: unit for unit in units},
        )

    @property
    def display_name(self) -> str:
        """Name for the Home Assistant device."""
        return self.address or self.name or f"AirByNature {self.id}"
