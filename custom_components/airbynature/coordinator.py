"""Data update coordinator for AirByNature."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AirByNatureClient, AirByNatureError, AuthError
from .const import DOMAIN, UPDATE_INTERVAL
from .models import DeviceGroup

_LOGGER = logging.getLogger(__name__)

type AirByNatureConfigEntry = ConfigEntry[AirByNatureCoordinator]


class AirByNatureCoordinator(DataUpdateCoordinator[dict[int, DeviceGroup]]):
    """Polls all device groups of one account."""

    config_entry: AirByNatureConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AirByNatureConfigEntry,
        client: AirByNatureClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, DeviceGroup]:
        try:
            groups = await self.client.async_get_groups()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AirByNatureError as err:
            raise UpdateFailed(f"Error communicating with AirByNature: {err}") from err
        return {group.id: group for group in groups}

    @callback
    def async_apply_group(self, group: DeviceGroup) -> None:
        """Store a group returned by a command without polling again."""
        self.async_set_updated_data({**self.data, group.id: group})
