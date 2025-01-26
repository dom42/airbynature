import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .airbynature import AirByNature

_LOGGER = logging.getLogger(__name__)


class AirByNatureApi:
    abn = None
    hass = None

    def __init__(self, hass):
        _LOGGER.info("Starting")
        self.abn = AirByNature()
        self.hass = hass

    async def login(self, username, password):
        login_valid = await self.hass.async_add_executor_job(
            self.abn.login,
            username,
            password,
        )

        if not login_valid:
            raise InvalidAuth

        profile_id = await self.hass.async_add_executor_job(self.abn.get_profile_id)

    async def get_data(self):
        devices = await self.hass.async_add_executor_job(self.abn.get_devices)
        _LOGGER.info(devices)
        return devices


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
