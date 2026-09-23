"""Sensor platform for AirByNature."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import AirByNatureGroupEntity, AirByNatureUnitEntity
from .models import DeviceGroup, Unit

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirByNatureGroupSensorDescription(SensorEntityDescription):
    """Describes a device group sensor."""

    value_fn: Callable[[DeviceGroup], StateType | datetime]


@dataclass(frozen=True, kw_only=True)
class AirByNatureUnitSensorDescription(SensorEntityDescription):
    """Describes a unit sensor."""

    value_fn: Callable[[Unit], StateType | datetime]
    requires_online: bool = True


def _temperature(
    key: str, value_fn: Callable[[Unit], StateType]
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=value_fn,
    )


def _humidity(
    key: str, value_fn: Callable[[Unit], StateType]
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=value_fn,
    )


def _fan_percent(
    key: str, value_fn: Callable[[Unit], StateType]
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value_fn,
    )


def _rpm(
    key: str, value_fn: Callable[[Unit], StateType], *, enabled: bool = True
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
        value_fn=value_fn,
    )


def _speed_factor(
    key: str, value_fn: Callable[[Unit], StateType]
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        value_fn=value_fn,
    )


GROUP_SENSORS: tuple[AirByNatureGroupSensorDescription, ...] = (
    AirByNatureGroupSensorDescription(
        key="avg_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda group: group.avg_temp,
    ),
    AirByNatureGroupSensorDescription(
        key="mode",
        value_fn=lambda group: group.mode,
    ),
    AirByNatureGroupSensorDescription(
        key="current_rule",
        value_fn=lambda group: group.current_running_rule,
    ),
    AirByNatureGroupSensorDescription(
        key="pause_inlets_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda group: group.pause_inlets_until,
    ),
    AirByNatureGroupSensorDescription(
        key="pause_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda group: group.pause_until,
    ),
    AirByNatureGroupSensorDescription(
        key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda group: group.status,
    ),
)

UNIT_SENSORS: tuple[AirByNatureUnitSensorDescription, ...] = (
    _temperature("inlet_temperature", lambda unit: unit.measurements.inlet_temp),
    _temperature("outlet_temperature", lambda unit: unit.measurements.outlet_temp),
    _temperature("external_temperature", lambda unit: unit.measurements.external_temp),
    _humidity("inlet_humidity", lambda unit: unit.measurements.inlet_humid),
    _humidity("outlet_humidity", lambda unit: unit.measurements.outlet_humid),
    AirByNatureUnitSensorDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda unit: unit.measurements.outlet_co2,
    ),
    AirByNatureUnitSensorDescription(
        key="tvoc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda unit: unit.measurements.outlet_tvoc,
    ),
    _fan_percent("inlet_fan", lambda unit: unit.measurements.inlet_fan),
    _fan_percent("outlet_fan", lambda unit: unit.measurements.outlet_fan),
    _rpm("inlet_fan1_rpm", lambda unit: unit.measurements.inlet_fan1_rpm),
    _rpm("outlet_fan1_rpm", lambda unit: unit.measurements.outlet_fan1_rpm),
    _rpm("inlet_fan2_rpm", lambda unit: unit.measurements.inlet_fan2_rpm, enabled=False),
    _rpm(
        "outlet_fan2_rpm", lambda unit: unit.measurements.outlet_fan2_rpm, enabled=False
    ),
    AirByNatureUnitSensorDescription(
        key="last_measurement",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        value_fn=lambda unit: unit.measurements.measured_at,
    ),
    AirByNatureUnitSensorDescription(
        key="wifi_signal",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        value_fn=lambda unit: unit.wifi_signal,
    ),
    _speed_factor("inlet_speed_factor", lambda unit: unit.inlet_speed_factor),
    _speed_factor("outlet_speed_factor", lambda unit: unit.outlet_speed_factor),
    AirByNatureUnitSensorDescription(
        key="interval",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        value_fn=lambda unit: unit.current_interval,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirByNatureConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirByNature sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for group_id, group in coordinator.data.items():
        entities.extend(
            AirByNatureGroupSensor(coordinator, group_id, description)
            for description in GROUP_SENSORS
        )
        for unit_id in group.units:
            entities.extend(
                AirByNatureUnitSensor(coordinator, group_id, unit_id, description)
                for description in UNIT_SENSORS
            )
    async_add_entities(entities)


class AirByNatureGroupSensor(AirByNatureGroupEntity, SensorEntity):
    """Sensor for a device group value."""

    entity_description: AirByNatureGroupSensorDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        description: AirByNatureGroupSensorDescription,
    ) -> None:
        super().__init__(coordinator, group_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.group)


class AirByNatureUnitSensor(AirByNatureUnitEntity, SensorEntity):
    """Sensor for a unit value."""

    entity_description: AirByNatureUnitSensorDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        unit_id: int,
        description: AirByNatureUnitSensorDescription,
    ) -> None:
        super().__init__(coordinator, group_id, unit_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self.unit.is_online or not self.entity_description.requires_online

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.unit)
