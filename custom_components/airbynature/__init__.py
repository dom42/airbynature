from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import async_generate_entity_id, DeviceInfo
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.components import is_on
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.const import EVENT_SERVICE_REGISTERED
from homeassistant.const import CONF_API_KEY, CONF_NAME, Platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .const import (
    DOMAIN,
    )

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up this integration using YAML is not supported."""
    return True

# async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
#     """Set up this integration using UI."""
#     conf = entry.data
#     options = entry.options

#     _LOGGER.info("Async_setup_entry")
#     # _LOGGER.warning("Configuration received: %s", conf)

#      if hass.data.get(DOMAIN) is None:
#         hass.data.setdefault(DOMAIN, {})
    
#     _LOGGER.info("STARTUP config: [%s]", entry.options)


#  async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Handle removal of an entry."""
#     _LOGGER.info("Async_unload_entry")


# async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
#     """Reload config entry."""
#     _LOGGER.info("Async_reload_entry")
#     await async_unload_entry(hass, entry)
#     await async_setup_entry(hass, entry)