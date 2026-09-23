"""Config flow for the AirByNature integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AirByNatureClient, AirByNatureError, AuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def _async_get_user_id(hass: HomeAssistant, username: str, password: str) -> int:
    client = AirByNatureClient(async_get_clientsession(hass), username, password)
    await client.async_login()
    return await client.async_get_user_id()


class AirByNatureConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirByNature."""

    VERSION = 1

    async def _async_validate(
        self, username: str, password: str, errors: dict[str, str]
    ) -> int | None:
        """Return the user id, or None after filling ``errors``."""
        try:
            return await _async_get_user_id(self.hass, username, password)
        except AuthError:
            errors["base"] = "invalid_auth"
        except AirByNatureError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while validating credentials")
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the AirByNature app credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id = await self._async_validate(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], errors
            )
            if user_id is not None:
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication after the stored password stopped working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password for the existing account."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.data[CONF_USERNAME]
        if user_input is not None:
            user_id = await self._async_validate(
                username, user_input[CONF_PASSWORD], errors
            )
            if user_id is not None:
                await self.async_set_unique_id(str(user_id))
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={"username": username},
            errors=errors,
        )
