# import logging
# import voluptuous as vol

# from homeassistant.core import HomeAssistant
# from homeassistant.core import callback
# from homeassistant.data_entry_flow import FlowResult
# from homeassistant.const import (
#     CONF_EMAIL,
#     CONF_PASSWORD,
#     HTTP_BEARER_AUTHENTICATION
# )
# from homeassistant.helpers.entity_registry import (
#     async_entries_for_config_entry,
#     async_get,
# )
# from .const import (
#     DOMAIN,
# )

# _LOGGER = logging.getLogger(__name__)

# from homeassistant.helpers.selector import (
#     TextSelector,
#     TextSelectorConfig,
#     TextSelectorType,
# )

# NETWORK_SCHEMA = vol.Schema(
#     {
#         vol.Required(CONF_EMAIL): TextSelector(
#             TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="email")
#         ),
#         vol.Required(CONF_PASSWORD): TextSelector(
#             TextSelectorConfig(
#                 type=TextSelectorType.PASSWORD, autocomplete="current-password"
#             )
#         ),
#     }
# )

# async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, str]:
#     session = await hass.async_add_executor_job(
#         get_session,
#         data[CONF_EMAIL],
#         data[CONF_PASSWORD],
#     )
#     if not session:
#         raise InvalidLogin

#     _LOGGER.error("WHAT IS SESSION: %s", session)

#     await hass.async_add_executor_job(
#         todo,
#         )

#     return {
#     	HTTP_BEARER_AUTHENTICATION: b_token
#     }


# class AirByNatureConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
#     VERSION = 1

#     def __init__(self) -> None:
#         _LOGGER.warning("Init ConfigFLow")

#     async def async_step_user(self, user_input):
#         errors = {}

#         await self.async_set_unique_id(ABN_HAS_BEEN_SETUP)
#         self._abort_if_unique_id_configured()

#         if user_input is not None:
#             try:
#                 _LOGGER.warning("This is user_input: [%s]", user_input)

#                 info = await validate_input(self.hass, user_input)

#             except InvalidLogin:
#                 errors[CONF_EMAIL] = "cannot_connect"
#             except CouldNotCreate:
#                 errors[CONF_EMAIL] = "cannot_connect"

#         return self.async_show_form(
#             step_id="user", data_schema=NETWORK_SCHEMA, errors=errors
#         )

#     @staticmethod
#     @callback
#     def async_get_options_flow(
#         config_entry: config_entries.ConfigEntry,
#     ) -> config_entries.OptionsFlow:
#         """Create the options flow."""
#         return OptionsFlowHandler(config_entry)


# class InvalidLogin(exceptions.HomeAssistantError):
#     """Error to indicate there is an invalid username/password."""


# class CouldNotCreate(exceptions.HomeAssistantError):
#     """Error to indicate culd not create network."""


# class OptionsFlowHandler(config_entries.OptionsFlow):
#     def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
#         _LOGGER.info("Init OptionsConfigFlow")
#         self.config_entry = config_entry
#         self.options = dict(config_entry.options)

#     async def async_step_init(
#         self, user_input: dict[str, Any] | None = None
#     ) -> FlowResult:
#         """Manage the options."""
#         _LOGGER.info("Async step init options flow [%s]", self.options)

#         if user_input is not None:
#             _LOGGER.warning("User_input: [%s]", user_input)
#             self.options.update(user_input)
#             return await self._update_options()
