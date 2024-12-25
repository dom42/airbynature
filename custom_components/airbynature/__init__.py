"""The AirByNature integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


from .coordinator import AirByNatureCoordinator


from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


# TODO Update entry annotation
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up AirByNature from a config entry."""

    """Use config values to set up a function enabling status retrieval."""

    hass.data.setdefault(DOMAIN, {})

    coordinator = AirByNatureCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator for later uses.
    config_entry.runtime_data = coordinator

    # Forward the config entries to the supported platforms.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


# TODO Update entry annotation
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
