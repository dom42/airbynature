"""Number platform for AirByNature."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import AirByNatureClient
from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import AirByNatureGroupEntity, call_api
from .models import DeviceGroup, Permissions

PARALLEL_UPDATES = 1


def _utcnow() -> datetime:
    return dt_util.utcnow()


def remaining_hours(until: datetime | None, now: datetime) -> int:
    """Whole hours left until ``until``, rounded up; 0 when not in the future."""
    if until is None or until <= now:
        return 0
    return math.ceil((until - now).total_seconds() / 3600)


def _pause_until(hours: int) -> datetime | None:
    return _utcnow() + timedelta(hours=hours) if hours > 0 else None


@dataclass(frozen=True, kw_only=True)
class AirByNatureNumberDescription(NumberEntityDescription):
    """Describes a device group number."""

    permission_fn: Callable[[Permissions], bool]
    value_fn: Callable[[DeviceGroup], float | None]
    set_fn: Callable[[AirByNatureClient, int, int], Awaitable[DeviceGroup]]


NUMBERS: tuple[AirByNatureNumberDescription, ...] = (
    AirByNatureNumberDescription(
        key="target_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0,
        native_max_value=40,
        native_step=1,
        permission_fn=lambda permissions: permissions.can_change_temperature,
        value_fn=lambda group: group.target_temperature,
        set_fn=lambda client, group_id, value: client.async_set_target_temperature(
            group_id, value
        ),
    ),
    AirByNatureNumberDescription(
        key="pause_inlets",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=0,
        native_max_value=24,
        native_step=1,
        permission_fn=lambda permissions: permissions.can_pause_inlets,
        value_fn=lambda group: remaining_hours(group.pause_inlets_until, _utcnow()),
        set_fn=lambda client, group_id, value: client.async_set_pause_inlets(
            group_id, _pause_until(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirByNatureConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirByNature numbers."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirByNatureNumber(coordinator, group_id, description)
        for group_id, group in coordinator.data.items()
        for description in NUMBERS
        if description.permission_fn(group.permissions)
    )


class AirByNatureNumber(AirByNatureGroupEntity, NumberEntity):
    """Number controlling a device group setting."""

    entity_description: AirByNatureNumberDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        description: AirByNatureNumberDescription,
    ) -> None:
        super().__init__(coordinator, group_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.group)

    async def async_set_native_value(self, value: float) -> None:
        group = await call_api(
            self.entity_description.set_fn(
                self.coordinator.client, self.group_id, int(value)
            )
        )
        self.coordinator.async_apply_group(group)
