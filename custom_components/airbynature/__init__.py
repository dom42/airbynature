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
