"""Tests for AirByNature diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.diagnostics import (
    async_get_config_entry_diagnostics,
)

REDACTED = "**REDACTED**"


async def test_diagnostics_redacts_personal_data(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    result = await async_get_config_entry_diagnostics(hass, init_integration)

    assert result["entry"]["username"] == REDACTED
    assert result["entry"]["password"] == REDACTED
    group = result["groups"][0]
    assert group["address"] == REDACTED
    assert group["name"] == REDACTED
    assert group["target_temperature"] == 23
    assert group["units"][200]["measurements"]["outlet_co2"] == 440.3
