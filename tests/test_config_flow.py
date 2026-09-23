"""Tests for the AirByNature config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.api import ApiError, AuthError, CannotConnect
from custom_components.airbynature.const import DOMAIN

from .helpers import setup_integration

USER_INPUT = {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"}


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_flow_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@example.com"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "10"
    mock_flow_client.async_login.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AuthError("rejected"), "invalid_auth"),
        (CannotConnect("timeout"), "cannot_connect"),
        (ApiError("HTTP 500"), "cannot_connect"),
        (ValueError("bug"), "unknown"),
    ],
)
async def test_user_flow_errors_and_recovery(
    hass: HomeAssistant,
    mock_flow_client: MagicMock,
    mock_setup_entry: AsyncMock,
    error: Exception,
    expected: str,
) -> None:
    mock_flow_client.async_login.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    mock_flow_client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-secret"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"
    assert mock_config_entry.data[CONF_USERNAME] == "user@example.com"


async def test_reauth_invalid_password(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    mock_config_entry.add_to_hass(hass)
    mock_flow_client.async_login.side_effect = AuthError("rejected")
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flow_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    mock_config_entry.add_to_hass(hass)
    mock_flow_client.async_get_user_id.return_value = 99
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-secret"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_PASSWORD] == "secret"


async def test_auth_failure_during_setup_starts_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_get_groups.side_effect = AuthError("rejected")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["step_id"] == "reauth_confirm"
