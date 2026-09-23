"""The AirByNature integration."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AirByNatureClient
from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import group_device_info

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AirByNatureConfigEntry) -> bool:
    """Set up AirByNature from a config entry."""
    client = AirByNatureClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = AirByNatureCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register group devices first so unit devices can reference them via_device.
    device_registry = dr.async_get(hass)
    for group in coordinator.data.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **group_device_info(group)
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirByNatureConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
