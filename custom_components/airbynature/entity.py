"""Base entities for AirByNature."""

from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AirByNatureError
from .const import DOMAIN, MANUFACTURER
from .coordinator import AirByNatureCoordinator
from .models import DeviceGroup, Unit


def group_device_info(group: DeviceGroup) -> DeviceInfo:
    """Device info for a device group."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"group_{group.id}")},
        name=group.display_name,
        manufacturer=MANUFACTURER,
        model="Device group",
    )


def unit_device_info(group_id: int, unit: Unit) -> DeviceInfo:
    """Device info for a unit, linked to its group."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"unit_{unit.id}")},
        name=unit.name or f"Unit {unit.id}",
        manufacturer=MANUFACTURER,
        model=unit.type,
        serial_number=unit.serial_number,
        via_device=(DOMAIN, f"group_{group_id}"),
    )


async def call_api[T](request: Awaitable[T]) -> T:
    """Await an API command, turning client errors into HomeAssistantError."""
    try:
        return await request
    except AirByNatureError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"error": str(err)},
        ) from err


class AirByNatureGroupEntity(CoordinatorEntity[AirByNatureCoordinator]):
    """Entity belonging to a device group."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AirByNatureCoordinator, group_id: int, key: str
    ) -> None:
        super().__init__(coordinator)
        self.group_id = group_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{group_id}_{key}"
        self._attr_device_info = group_device_info(coordinator.data[group_id])

    @property
    def group(self) -> DeviceGroup:
        """Current data for this entity's group."""
        return self.coordinator.data[self.group_id]

    @property
    def available(self) -> bool:
        return super().available and self.group_id in self.coordinator.data


class AirByNatureUnitEntity(CoordinatorEntity[AirByNatureCoordinator]):
    """Entity belonging to a unit."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        unit_id: int,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self.group_id = group_id
        self.unit_id = unit_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{unit_id}_{key}"
        self._attr_device_info = unit_device_info(
            group_id, coordinator.data[group_id].units[unit_id]
        )

    @property
    def unit(self) -> Unit:
        """Current data for this entity's unit."""
        return self.coordinator.data[self.group_id].units[self.unit_id]

    @property
    def available(self) -> bool:
        group = self.coordinator.data.get(self.group_id)
        return super().available and group is not None and self.unit_id in group.units
