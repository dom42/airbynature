"""Binary sensor platform for AirByNature."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import AirByNatureGroupEntity, AirByNatureUnitEntity
from .models import DeviceGroup, Unit

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirByNatureGroupBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a device group binary sensor."""

    value_fn: Callable[[DeviceGroup], bool | None]


@dataclass(frozen=True, kw_only=True)
class AirByNatureUnitBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a unit binary sensor."""

    value_fn: Callable[[Unit], bool | None]


GROUP_BINARY_SENSORS: tuple[AirByNatureGroupBinarySensorDescription, ...] = (
    AirByNatureGroupBinarySensorDescription(
        key="rule_enabled",
        value_fn=lambda group: group.is_rule_enabled,
    ),
    AirByNatureGroupBinarySensorDescription(
        key="drying",
        value_fn=lambda group: group.is_drying,
    ),
)

UNIT_BINARY_SENSORS: tuple[AirByNatureUnitBinarySensorDescription, ...] = (
    AirByNatureUnitBinarySensorDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.is_online,
    ),
    AirByNatureUnitBinarySensorDescription(
        key="filter",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.has_filter,
    ),
    AirByNatureUnitBinarySensorDescription(
        key="drying_heat_exchanger",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.is_drying_heat_exchanger,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirByNatureConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirByNature binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for group_id, group in coordinator.data.items():
        entities.extend(
            AirByNatureGroupBinarySensor(coordinator, group_id, description)
            for description in GROUP_BINARY_SENSORS
        )
        for unit_id in group.units:
            entities.extend(
                AirByNatureUnitBinarySensor(coordinator, group_id, unit_id, description)
                for description in UNIT_BINARY_SENSORS
            )
    async_add_entities(entities)


class AirByNatureGroupBinarySensor(AirByNatureGroupEntity, BinarySensorEntity):
    """Binary sensor for a device group value."""

    entity_description: AirByNatureGroupBinarySensorDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        description: AirByNatureGroupBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, group_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.group)


class AirByNatureUnitBinarySensor(AirByNatureUnitEntity, BinarySensorEntity):
    """Binary sensor for a unit value (stays available while the unit is offline)."""

    entity_description: AirByNatureUnitBinarySensorDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        unit_id: int,
        description: AirByNatureUnitBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, group_id, unit_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.unit)
