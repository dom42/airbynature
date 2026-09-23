"""Config flow for the AirByNature integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class AirByNatureConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirByNature."""

    VERSION = 1
