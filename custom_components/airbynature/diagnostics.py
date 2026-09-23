"""Diagnostics support for AirByNature."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import AirByNatureConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, "address", "name"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirByNatureConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "groups": async_redact_data(
            [asdict(group) for group in entry.runtime_data.data.values()], TO_REDACT
        ),
    }
