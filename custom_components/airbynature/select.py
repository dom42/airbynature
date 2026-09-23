"""Select platform for AirByNature."""

from __future__ import annotations

from typing import Final

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import AirByNatureUnitEntity, call_api

PARALLEL_UPDATES = 1

# Position + 1 is the API comfort level (1 = off ... 6 = extra high).
COMFORT_LEVELS: Final = ["off", "very_quiet", "quiet", "normal", "high", "extra_high"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirByNatureConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirByNature selects."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirByNatureComfortLevelSelect(coordinator, group_id, unit_id)
        for group_id, group in coordinator.data.items()
        if group.permissions.can_change_comfort_level
        for unit_id in group.units
    )


class AirByNatureComfortLevelSelect(AirByNatureUnitEntity, SelectEntity):
    """Comfort level (fan speed) of one unit."""

    _attr_options = COMFORT_LEVELS

    def __init__(
        self, coordinator: AirByNatureCoordinator, group_id: int, unit_id: int
    ) -> None:
        super().__init__(coordinator, group_id, unit_id, "comfort_level")

    @property
    def current_option(self) -> str | None:
        level = self.unit.comfort_level
        if level is None or not 1 <= level <= len(COMFORT_LEVELS):
            return None
        return COMFORT_LEVELS[level - 1]

    async def async_select_option(self, option: str) -> None:
        await call_api(
            self.coordinator.client.async_set_comfort_level(
                self.group_id, self.unit_id, COMFORT_LEVELS.index(option) + 1
            )
        )
        await self.coordinator.async_request_refresh()
