# AirByNature Integration Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the AirByNature Home Assistant custom integration with a clean rewrite that exposes each device group as a device, each ventilation unit as a child device, all API values as correctly typed entities, and target temperature / comfort level / inlet pause as controls.

**Architecture:** An async `aiohttp` client (`api.py`) parses responses into frozen dataclasses (`models.py`). One `DataUpdateCoordinator` per config entry polls every 60 s and holds `dict[group_id, DeviceGroup]`. Entities are generated from entity-description tables whose `value_fn` reads the dataclasses; group and unit base entities own `DeviceInfo` and unique IDs.

**Tech Stack:** Python 3.13, Home Assistant ≥ 2025.1.0, aiohttp (HA shared session), pytest + pytest-homeassistant-custom-component, aioresponses, GitHub Actions (hassfest, HACS action).

**Spec:** `docs/superpowers/specs/2026-09-23-airbynature-rewrite-design.md`

## Global Constraints

- Branch: `rewrite`. Never touch `main`.
- Never stage `notes_donot_commit.txt` (contains credentials) or `custom_components/airbynature/no_flo.backup` (user's untracked backup; do not delete it either). Always `git add` explicit paths, never `git add -A` / `git add .`.
- `hacs.json` `homeassistant` minimum: `"2025.1.0"`. Only use HA APIs available in 2025.1.
- `manifest.json`: `integration_type: hub`, `iot_class: cloud_polling`, `requirements: []`, `version: 0.1.0`.
- `api.py` and `models.py` import nothing from `homeassistant`.
- HTTP only through the session passed in (HA: `async_get_clientsession(hass)`). Request timeout 10 s. Poll interval 60 s.
- Token is held in memory only, never written to the config entry.
- Unique IDs: group entities `f"{group_id}_{key}"`, unit entities `f"{unit_id}_{key}"`. Device identifiers: `(DOMAIN, f"group_{group_id}")`, `(DOMAIN, f"unit_{unit_id}")`.
- All entity names come from `translation_key` (= description key) with English and Danish translations.
- Controls are created only when the matching permission in `meta.permissions` is true.
- Test fixtures use fake data only: user id `10`, e-mail `user@example.com`, group id `100`, name `Test User`, address `Testvej 1`, unit id `200` named `Loftanlæg`.
- Every commit message ends with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Deliberate deviations from the spec (apply them, do not "fix" them back):
  - `mode` is a plain text sensor, not `SensorDeviceClass.ENUM`: the full set of API values is unknown and ENUM raises on unlisted values.
  - The coordinator does not override `_async_setup`; the client logs in lazily on its first request, which is equivalent and simpler.
  - The group device is registered in `async_setup_entry` before platforms load, so unit devices' `via_device` always points at an existing device.

## Review Focus

1. A unit that has never reported (`latest_history` null or missing) → its measurement sensors show `unknown`, nothing crashes. Pinned in Task 1 (`test_missing_latest_history`) and Task 4 (`test_unit_without_history`).
2. A `mode` value never seen before (e.g. `"away"`) → shown verbatim. Pinned in Task 4 (`test_unknown_mode_is_shown_verbatim`).
3. An inlet pause set from the app for longer than 24 h, or one that has already expired → Pause inlets number shows the remaining hours (possibly > 24) or 0, no exception. Pinned in Task 6 (`test_remaining_hours`, `test_pause_longer_than_max`).
4. `comfort_level` null or outside 1–6 → Comfort level select shows `unknown`. Pinned in Task 7 (`test_comfort_level_out_of_range`).
5. An account with zero device groups → integration loads with no devices. Pinned in Task 3 (`test_account_without_groups`).

---

## File Structure

| File | Responsibility |
|---|---|
| `custom_components/__init__.py` | Makes `custom_components` importable for tests |
| `custom_components/airbynature/__init__.py` | Setup/unload entry, register group devices, forward platforms |
| `custom_components/airbynature/const.py` | `DOMAIN`, `MANUFACTURER`, `UPDATE_INTERVAL` |
| `custom_components/airbynature/models.py` | Dataclasses + parsing of API JSON |
| `custom_components/airbynature/api.py` | Async HTTP client and exceptions |
| `custom_components/airbynature/coordinator.py` | `AirByNatureCoordinator`, `AirByNatureConfigEntry` |
| `custom_components/airbynature/entity.py` | Base entities, `DeviceInfo` builders, `call_api` |
| `custom_components/airbynature/sensor.py` | Sensor descriptions + entities |
| `custom_components/airbynature/binary_sensor.py` | Binary sensor descriptions + entities |
| `custom_components/airbynature/number.py` | Target temperature + pause inlets |
| `custom_components/airbynature/select.py` | Comfort level |
| `custom_components/airbynature/config_flow.py` | User + reauth steps |
| `custom_components/airbynature/diagnostics.py` | Redacted diagnostics |
| `custom_components/airbynature/strings.json`, `translations/en.json`, `translations/da.json`, `icons.json` | Texts and icons |
| `tests/helpers.py` | `load_json`, `entity_id`, `setup_integration` |
| `tests/conftest.py` | Shared fixtures |
| `tests/fixtures/*.json` | Sanitised API responses |

---

### Task 1: Scaffolding, test harness and models

**Files:**
- Delete (git rm): `custom_components/airbynature/AirByNatureApi.py`, `airbynature.py`, `coordinator.py`, `sensor.py`, `config_flow.py`
- Modify: `custom_components/airbynature/__init__.py` (replace whole file), `custom_components/airbynature/const.py`, `custom_components/airbynature/manifest.json`, `.gitignore`
- Create: `custom_components/__init__.py`, `custom_components/airbynature/models.py`, `pyproject.toml`, `requirements_test.txt`, `tests/__init__.py`, `tests/helpers.py`, `tests/conftest.py`, `tests/fixtures/{token,profile,groups,group,unit_patch}.json`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `DeviceGroup.from_api(body: dict) -> DeviceGroup` (body is the full response incl. `data` and `meta`), `DeviceGroup.display_name -> str`, `DeviceGroup.units: dict[int, Unit]`, `Unit`, `Measurements`, `Permissions`; `const.DOMAIN`, `const.MANUFACTURER`, `const.UPDATE_INTERVAL`; test helpers `load_json(name) -> dict`, `entity_id(hass, platform, unique_id) -> str`, `async setup_integration(hass, entry) -> None`; fixtures `group_payload`, `mock_config_entry`, `mock_client`, `init_integration`, `mock_setup_entry`, `mock_flow_client`.

- [ ] **Step 1: Remove old code and write minimal package files**

```bash
cd /home/tonne/git/airbynature
git rm -q custom_components/airbynature/AirByNatureApi.py custom_components/airbynature/airbynature.py custom_components/airbynature/coordinator.py custom_components/airbynature/sensor.py custom_components/airbynature/config_flow.py
```

`custom_components/airbynature/__init__.py` (whole file; replaced in Task 3):

```python
"""The AirByNature integration."""
```

`custom_components/__init__.py`:

```python
"""Custom integrations."""
```

`custom_components/airbynature/const.py`:

```python
"""Constants for the AirByNature integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "airbynature"
MANUFACTURER: Final = "AirByNature"
UPDATE_INTERVAL: Final = timedelta(seconds=60)
```

`custom_components/airbynature/manifest.json`:

```json
{
  "domain": "airbynature",
  "name": "AirByNature",
  "codeowners": ["@dom42"],
  "config_flow": true,
  "documentation": "https://github.com/dom42/airbynature",
  "integration_type": "hub",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/dom42/airbynature/issues",
  "requirements": [],
  "version": "0.1.0"
}
```

Append to `.gitignore`:

```
notes_donot_commit.txt
*.backup
.pytest_cache
```

- [ ] **Step 2: Test tooling**

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
pythonpath = ["."]
testpaths = ["tests"]
```

`requirements_test.txt`:

```
pytest-homeassistant-custom-component
aioresponses
```

Create the virtualenv (installing `uv` needs the user's approval if it is missing):

```bash
command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements_test.txt
```

Expected: install finishes; `.venv/bin/pytest --version` prints a version.

- [ ] **Step 3: Fixtures**

`tests/__init__.py`:

```python
"""Tests for the AirByNature integration."""
```

`tests/fixtures/token.json`:

```json
{"token_type": "Bearer", "expires_in": 31536000, "access_token": "test-token", "refresh_token": "test-refresh"}
```

`tests/fixtures/profile.json`:

```json
{"data": {"id": 10, "firstname": "", "email": "user@example.com", "phonenr": null, "lastname": null, "is_admin": false}, "meta": {"permissions": {"all": false, "isSuperAdmin": false, "hasAccessToAdminPanel": false}}}
```

`tests/fixtures/groups.json`:

```json
{"data": [{"id": 100, "name": "Test User"}]}
```

`tests/fixtures/group.json`:

```json
{
  "data": {
    "id": 100,
    "name": "Test User",
    "address": "Testvej 1",
    "postcode": "1000",
    "city": "Testby",
    "target_temperature": 23,
    "current_running_rule": "Svale 1 - Fugt 1 (>55%)",
    "is_rule_enabled": 1,
    "mode": "comfort",
    "pause_until": null,
    "pause_inlets_until": null,
    "pause_time": [{"active": false, "day": 1, "start_time": "10:00", "end_time": "15:00"}],
    "avg_temp": "25.90",
    "is_drying": 0,
    "status": "ok",
    "schedule": null,
    "devices": [
      {
        "id": 200,
        "group_id": 100,
        "name": "Loftanlæg",
        "type": "main-v2",
        "outlet_speed_factor": "65.00",
        "inlet_speed_factor": "55.00",
        "has_filter": 1,
        "comfort_level": 3,
        "use_for_avg_temp": 1,
        "is_online": true,
        "wifi_signal": 28,
        "dry_heat_exchanger_until": null,
        "is_drying_heat_exchanger": false,
        "current_interval": 60,
        "serial_number": null,
        "last_handshake_at": null,
        "latest_history": {
          "device_id": 200,
          "inlet_temp": 23.89,
          "inlet_humid": 60.3,
          "inlet_fan": 0,
          "inlet_fan1_rpm": 0,
          "inlet_fan2_rpm": 0,
          "outlet_temp": 25.9,
          "outlet_humid": 55.3,
          "outlet_co2": 440.3,
          "outlet_fan": 74,
          "outlet_tvoc": 46.9,
          "outlet_fan1_rpm": 3617,
          "outlet_fan2_rpm": 0,
          "external_temp": 24.97,
          "created_at": "2024-09-24T16:00:28.000000Z"
        },
        "latest_diagnostic": {"device_id": 200, "wifi_signal": "30", "created_at": "2024-09-24T16:00:19.000000Z"}
      }
    ],
    "users": [{"id": 10, "firstname": "", "email": "user@example.com", "phonenr": null, "lastname": null, "is_admin": false}]
  },
  "meta": {
    "permissions": {
      "canChangeTemperature": true,
      "canChangeMode": false,
      "canChangeAirCirculationLevel": true,
      "canChangeSchedule": true,
      "canViewHistory": true,
      "canAdministerDeviceGroup": false,
      "canAccessDeviceGroup": true,
      "canPauseInlets": true
    }
  }
}
```

`tests/fixtures/unit_patch.json`:

```json
{"data": {"id": 200, "name": "Loftanlæg", "type": "main-v2", "comfort_level": 5, "latest_history": {"inlet_temp": 23.93, "inlet_humid": 60.18, "inlet_co2": null, "inlet_fan": 0, "inlet_fan1_rpm": 0, "inlet_fan2_rpm": 0, "outlet_temp": 25.94, "outlet_humid": 55.22, "outlet_co2": 440.18, "outlet_fan": 74, "outlet_fan1_rpm": 3618, "outlet_fan2_rpm": 0, "outlet_tvoc": 46.94, "created_at": "2024-09-24T16:02:28.000000Z"}}}
```

- [ ] **Step 4: Test helpers and conftest**

`tests/helpers.py`:

```python
"""Helpers for AirByNature tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.const import DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"


def load_json(name: str) -> dict[str, Any]:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    """Return the entity_id registered for a unique_id."""
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert found is not None, f"no {platform} entity with unique_id {unique_id}"
    return found


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add and set up a config entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
```

`tests/conftest.py`:

```python
"""Fixtures for AirByNature tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.const import DOMAIN
from custom_components.airbynature.models import DeviceGroup

from .helpers import load_json, setup_integration


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in all tests."""


@pytest.fixture
def group_payload() -> dict[str, Any]:
    """Return a fresh copy of the group detail response."""
    return load_json("group.json")


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the test account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="user@example.com",
        unique_id="10",
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )


@pytest.fixture
def mock_client(group_payload: dict[str, Any]) -> Generator[MagicMock]:
    """Patch the API client used by the integration setup."""
    with patch(
        "custom_components.airbynature.AirByNatureClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]
        client.async_get_user_id.return_value = 10
        client.async_set_target_temperature.return_value = DeviceGroup.from_api(
            group_payload
        )
        client.async_set_pause_inlets.return_value = DeviceGroup.from_api(
            group_payload
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> MockConfigEntry:
    """Set up the integration with the mocked client."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config flow tests from setting up the integration."""
    with patch(
        "custom_components.airbynature.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
def mock_flow_client() -> Generator[MagicMock]:
    """Patch the API client used by the config flow."""
    with patch(
        "custom_components.airbynature.config_flow.AirByNatureClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.async_get_user_id.return_value = 10
        yield client
```

(`mock_client`, `init_integration`, `mock_setup_entry` and `mock_flow_client` are only used from Task 3 onward; the patch targets are resolved lazily when a test requests them.)

- [ ] **Step 5: Write the failing model tests**

`tests/test_models.py`:

```python
"""Tests for AirByNature model parsing."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from custom_components.airbynature.models import DeviceGroup


def test_parse_group(group_payload: dict[str, Any]) -> None:
    group = DeviceGroup.from_api(group_payload)

    assert group.id == 100
    assert group.name == "Test User"
    assert group.display_name == "Testvej 1"
    assert group.target_temperature == 23
    assert group.avg_temp == 25.9
    assert group.mode == "comfort"
    assert group.current_running_rule == "Svale 1 - Fugt 1 (>55%)"
    assert group.is_rule_enabled is True
    assert group.is_drying is False
    assert group.status == "ok"
    assert group.pause_until is None
    assert group.pause_inlets_until is None
    assert group.permissions.can_change_temperature is True
    assert group.permissions.can_change_mode is False
    assert group.permissions.can_change_comfort_level is True
    assert group.permissions.can_pause_inlets is True


def test_parse_unit(group_payload: dict[str, Any]) -> None:
    unit = DeviceGroup.from_api(group_payload).units[200]

    assert unit.name == "Loftanlæg"
    assert unit.type == "main-v2"
    assert unit.comfort_level == 3
    assert unit.is_online is True
    assert unit.wifi_signal == 28
    assert unit.inlet_speed_factor == 55.0
    assert unit.outlet_speed_factor == 65.0
    assert unit.has_filter is True
    assert unit.is_drying_heat_exchanger is False
    assert unit.current_interval == 60
    assert unit.serial_number is None
    m = unit.measurements
    assert m.inlet_temp == 23.89
    assert m.inlet_humid == 60.3
    assert m.inlet_fan == 0
    assert m.outlet_temp == 25.9
    assert m.outlet_humid == 55.3
    assert m.outlet_co2 == 440.3
    assert m.outlet_fan == 74
    assert m.outlet_tvoc == 46.9
    assert m.outlet_fan1_rpm == 3617
    assert m.outlet_fan2_rpm == 0
    assert m.external_temp == 24.97
    assert m.measured_at == datetime(2024, 9, 24, 16, 0, 28, tzinfo=UTC)


def test_parse_pause_timestamp(group_payload: dict[str, Any]) -> None:
    group_payload["data"]["pause_inlets_until"] = "2024-09-24T16:59:33.000000Z"

    group = DeviceGroup.from_api(group_payload)

    assert group.pause_inlets_until == datetime(2024, 9, 24, 16, 59, 33, tzinfo=UTC)


@pytest.mark.parametrize("history", [None, "missing"])
def test_missing_latest_history(group_payload: dict[str, Any], history: Any) -> None:
    device = group_payload["data"]["devices"][0]
    if history == "missing":
        del device["latest_history"]
    else:
        device["latest_history"] = history

    m = DeviceGroup.from_api(group_payload).units[200].measurements

    assert m.inlet_temp is None
    assert m.outlet_co2 is None
    assert m.measured_at is None


@pytest.mark.parametrize("value", ["", "n/a", None])
def test_invalid_numbers_become_none(group_payload: dict[str, Any], value: Any) -> None:
    group_payload["data"]["avg_temp"] = value
    group_payload["data"]["devices"][0]["outlet_speed_factor"] = value

    group = DeviceGroup.from_api(group_payload)

    assert group.avg_temp is None
    assert group.units[200].outlet_speed_factor is None


@pytest.mark.parametrize("address", ["", None])
def test_display_name_falls_back_to_name(
    group_payload: dict[str, Any], address: str | None
) -> None:
    group_payload["data"]["address"] = address

    assert DeviceGroup.from_api(group_payload).display_name == "Test User"


def test_missing_meta_grants_no_permissions(group_payload: dict[str, Any]) -> None:
    del group_payload["meta"]

    permissions = DeviceGroup.from_api(group_payload).permissions

    assert permissions.can_change_temperature is False
    assert permissions.can_change_comfort_level is False
    assert permissions.can_pause_inlets is False


def test_group_without_devices(group_payload: dict[str, Any]) -> None:
    group_payload["data"]["devices"] = []

    assert DeviceGroup.from_api(group_payload).units == {}
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'custom_components.airbynature.models'`.

- [ ] **Step 7: Implement `models.py`**

`custom_components/airbynature/models.py`:

```python
"""Typed models for AirByNature API responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    return None if number is None else int(number)


def _bool(value: Any) -> bool | None:
    return None if value is None else bool(value)


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Permissions:
    """What the account may change on a device group."""

    can_change_temperature: bool
    can_change_mode: bool
    can_change_comfort_level: bool
    can_pause_inlets: bool

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> Permissions:
        data = data or {}
        return cls(
            can_change_temperature=bool(data.get("canChangeTemperature")),
            can_change_mode=bool(data.get("canChangeMode")),
            can_change_comfort_level=bool(data.get("canChangeAirCirculationLevel")),
            can_pause_inlets=bool(data.get("canPauseInlets")),
        )


@dataclass(frozen=True, slots=True)
class Measurements:
    """Latest measurements reported by a unit."""

    inlet_temp: float | None = None
    inlet_humid: float | None = None
    inlet_fan: int | None = None
    inlet_fan1_rpm: int | None = None
    inlet_fan2_rpm: int | None = None
    outlet_temp: float | None = None
    outlet_humid: float | None = None
    outlet_co2: float | None = None
    outlet_fan: int | None = None
    outlet_tvoc: float | None = None
    outlet_fan1_rpm: int | None = None
    outlet_fan2_rpm: int | None = None
    external_temp: float | None = None
    measured_at: datetime | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> Measurements:
        data = data or {}
        return cls(
            inlet_temp=_float(data.get("inlet_temp")),
            inlet_humid=_float(data.get("inlet_humid")),
            inlet_fan=_int(data.get("inlet_fan")),
            inlet_fan1_rpm=_int(data.get("inlet_fan1_rpm")),
            inlet_fan2_rpm=_int(data.get("inlet_fan2_rpm")),
            outlet_temp=_float(data.get("outlet_temp")),
            outlet_humid=_float(data.get("outlet_humid")),
            outlet_co2=_float(data.get("outlet_co2")),
            outlet_fan=_int(data.get("outlet_fan")),
            outlet_tvoc=_float(data.get("outlet_tvoc")),
            outlet_fan1_rpm=_int(data.get("outlet_fan1_rpm")),
            outlet_fan2_rpm=_int(data.get("outlet_fan2_rpm")),
            external_temp=_float(data.get("external_temp")),
            measured_at=_datetime(data.get("created_at")),
        )


@dataclass(frozen=True, slots=True)
class Unit:
    """A physical ventilation unit in a device group."""

    id: int
    name: str
    type: str | None
    comfort_level: int | None
    is_online: bool
    wifi_signal: int | None
    inlet_speed_factor: float | None
    outlet_speed_factor: float | None
    has_filter: bool | None
    is_drying_heat_exchanger: bool | None
    current_interval: int | None
    serial_number: str | None
    measurements: Measurements

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Unit:
        return cls(
            id=int(data["id"]),
            name=data.get("name") or "",
            type=data.get("type"),
            comfort_level=_int(data.get("comfort_level")),
            is_online=bool(data.get("is_online")),
            wifi_signal=_int(data.get("wifi_signal")),
            inlet_speed_factor=_float(data.get("inlet_speed_factor")),
            outlet_speed_factor=_float(data.get("outlet_speed_factor")),
            has_filter=_bool(data.get("has_filter")),
            is_drying_heat_exchanger=_bool(data.get("is_drying_heat_exchanger")),
            current_interval=_int(data.get("current_interval")),
            serial_number=data.get("serial_number"),
            measurements=Measurements.from_api(data.get("latest_history")),
        )


@dataclass(frozen=True, slots=True)
class DeviceGroup:
    """A device group (an address) with its units."""

    id: int
    name: str
    address: str | None
    target_temperature: float | None
    avg_temp: float | None
    mode: str | None
    current_running_rule: str | None
    is_rule_enabled: bool | None
    is_drying: bool | None
    status: str | None
    pause_until: datetime | None
    pause_inlets_until: datetime | None
    permissions: Permissions
    units: dict[int, Unit]

    @classmethod
    def from_api(cls, body: dict[str, Any]) -> DeviceGroup:
        """Parse a full group response (``data`` and ``meta``)."""
        data = body["data"]
        units = (Unit.from_api(device) for device in data.get("devices") or [])
        return cls(
            id=int(data["id"]),
            name=data.get("name") or "",
            address=data.get("address") or None,
            target_temperature=_float(data.get("target_temperature")),
            avg_temp=_float(data.get("avg_temp")),
            mode=data.get("mode"),
            current_running_rule=data.get("current_running_rule"),
            is_rule_enabled=_bool(data.get("is_rule_enabled")),
            is_drying=_bool(data.get("is_drying")),
            status=data.get("status"),
            pause_until=_datetime(data.get("pause_until")),
            pause_inlets_until=_datetime(data.get("pause_inlets_until")),
            permissions=Permissions.from_api(
                (body.get("meta") or {}).get("permissions")
            ),
            units={unit.id: unit for unit in units},
        )

    @property
    def display_name(self) -> str:
        """Name for the Home Assistant device."""
        return self.address or self.name or f"AirByNature {self.id}"
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add .gitignore pyproject.toml requirements_test.txt custom_components/__init__.py custom_components/airbynature/__init__.py custom_components/airbynature/const.py custom_components/airbynature/manifest.json custom_components/airbynature/models.py tests/
git commit -m "Start rewrite: remove old code, add models and test harness

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(The `git rm` from Step 1 is already staged.)

---

### Task 2: API client

**Files:**
- Create: `custom_components/airbynature/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `DeviceGroup.from_api(body)` from Task 1.
- Produces: `BASE_URL: str`; exceptions `AirByNatureError`, `AuthError(AirByNatureError)`, `CannotConnect(AirByNatureError)`, `ApiError(AirByNatureError)`; `AirByNatureClient(session: aiohttp.ClientSession, username: str, password: str)` with
  - `async async_login() -> None`
  - `async async_get_user_id() -> int`
  - `async async_get_groups() -> list[DeviceGroup]`
  - `async async_get_group(group_id: int) -> DeviceGroup`
  - `async async_set_target_temperature(group_id: int, value: int) -> DeviceGroup`
  - `async async_set_pause_inlets(group_id: int, until: datetime | None) -> DeviceGroup`
  - `async async_set_comfort_level(group_id: int, unit_id: int, level: int) -> None`

- [ ] **Step 1: Write the failing tests**

`tests/test_api.py`:

```python
"""Tests for the AirByNature API client."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime

import aiohttp
import pytest
from aioresponses import aioresponses
from yarl import URL

from custom_components.airbynature.api import (
    BASE_URL,
    AirByNatureClient,
    ApiError,
    AuthError,
    CannotConnect,
)

from .helpers import load_json

TOKEN_URL = f"{BASE_URL}/oauth/token"
PROFILE_URL = f"{BASE_URL}/api/profile"
GROUPS_URL = f"{BASE_URL}/api/user-app/devicegroups"
GROUP_URL = f"{GROUPS_URL}/100"
UNIT_URL = f"{GROUP_URL}/devices/200"


@pytest.fixture
async def client() -> AsyncGenerator[AirByNatureClient]:
    async with aiohttp.ClientSession() as session:
        yield AirByNatureClient(session, "user@example.com", "secret")


@pytest.fixture
def mocked() -> Generator[aioresponses]:
    with aioresponses() as mock:
        yield mock


def _calls(mocked: aioresponses, method: str, url: str) -> list:
    return mocked.requests[(method, URL(url))]


async def test_login_sends_password_grant(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"))

    await client.async_login()

    form = _calls(mocked, "POST", TOKEN_URL)[0].kwargs["data"]
    assert form["grant_type"] == "password"
    assert form["username"] == "user@example.com"
    assert form["password"] == "secret"
    assert form["client_id"] == "1"
    assert form["client_secret"] == "angular-app"


@pytest.mark.parametrize("status", [400, 401])
async def test_login_rejected(
    client: AirByNatureClient, mocked: aioresponses, status: int
) -> None:
    mocked.post(TOKEN_URL, status=status, payload={"error": "invalid_grant"})

    with pytest.raises(AuthError):
        await client.async_login()


async def test_login_server_error(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, status=500)

    with pytest.raises(ApiError):
        await client.async_login()


async def test_login_timeout(client: AirByNatureClient, mocked: aioresponses) -> None:
    mocked.post(TOKEN_URL, exception=TimeoutError())

    with pytest.raises(CannotConnect):
        await client.async_login()


async def test_request_logs_in_lazily_and_sends_token(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"))
    mocked.get(PROFILE_URL, payload=load_json("profile.json"))

    assert await client.async_get_user_id() == 10

    headers = _calls(mocked, "GET", PROFILE_URL)[0].kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-token"


async def test_401_relogs_in_once_and_retries(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"), repeat=True)
    mocked.get(PROFILE_URL, status=401)
    mocked.get(PROFILE_URL, payload=load_json("profile.json"))

    assert await client.async_get_user_id() == 10

    assert len(_calls(mocked, "POST", TOKEN_URL)) == 2
    assert len(_calls(mocked, "GET", PROFILE_URL)) == 2


async def test_401_after_relogin_raises_auth_error(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"), repeat=True)
    mocked.get(PROFILE_URL, status=401, repeat=True)

    with pytest.raises(AuthError):
        await client.async_get_user_id()


async def test_server_error_raises_api_error(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"))
    mocked.get(PROFILE_URL, status=500)

    with pytest.raises(ApiError):
        await client.async_get_user_id()


async def test_connection_error_raises_cannot_connect(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"))
    mocked.get(PROFILE_URL, exception=aiohttp.ClientConnectionError())

    with pytest.raises(CannotConnect):
        await client.async_get_user_id()


async def test_get_groups_fetches_each_group(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"))
    mocked.get(GROUPS_URL, payload=load_json("groups.json"))
    mocked.get(GROUP_URL, payload=load_json("group.json"))

    groups = await client.async_get_groups()

    assert [group.id for group in groups] == [100]
    assert groups[0].units[200].name == "Loftanlæg"


async def test_set_target_temperature(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"))
    mocked.put(GROUP_URL, payload=load_json("group.json"))

    group = await client.async_set_target_temperature(100, 21)

    assert _calls(mocked, "PUT", GROUP_URL)[0].kwargs["json"] == {
        "target_temperature": 21
    }
    assert group.id == 100


async def test_set_pause_inlets(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"))
    mocked.put(GROUP_URL, payload=load_json("group.json"))

    await client.async_set_pause_inlets(100, datetime(2024, 9, 24, 18, 0, tzinfo=UTC))

    assert _calls(mocked, "PUT", GROUP_URL)[0].kwargs["json"] == {
        "pause_inlets_until": "2024-09-24T18:00:00.000Z"
    }


async def test_stop_pause_inlets(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"))
    mocked.put(GROUP_URL, payload=load_json("group.json"))

    await client.async_set_pause_inlets(100, None)

    assert _calls(mocked, "PUT", GROUP_URL)[0].kwargs["json"] == {
        "pause_inlets_until": None
    }


async def test_set_comfort_level(
    client: AirByNatureClient, mocked: aioresponses
) -> None:
    mocked.post(TOKEN_URL, payload=load_json("token.json"))
    mocked.patch(UNIT_URL, payload=load_json("unit_patch.json"))

    await client.async_set_comfort_level(100, 200, 5)

    assert _calls(mocked, "PATCH", UNIT_URL)[0].kwargs["json"] == {
        "comfort_level": 5
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_api.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'custom_components.airbynature.api'`.

- [ ] **Step 3: Implement `api.py`**

`custom_components/airbynature/api.py`:

```python
"""Async client for the AirByNature cloud API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aiohttp

from .models import DeviceGroup

BASE_URL = "https://admin.airbynature.com"
TIMEOUT = aiohttp.ClientTimeout(total=10)


class AirByNatureError(Exception):
    """Base error for the AirByNature client."""


class AuthError(AirByNatureError):
    """Credentials or token were rejected."""


class CannotConnect(AirByNatureError):
    """The service could not be reached."""


class ApiError(AirByNatureError):
    """The service returned an unexpected response."""


class AirByNatureClient:
    """Client for the AirByNature user app API."""

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None

    async def async_login(self) -> None:
        """Obtain an access token."""
        form = {
            "grant_type": "password",
            "scope": "*",
            "username": self._username,
            "password": self._password,
            "client_id": "1",
            "client_secret": "angular-app",
        }
        try:
            async with self._session.post(
                f"{BASE_URL}/oauth/token",
                data=form,
                headers={"Accept": "application/json"},
                timeout=TIMEOUT,
            ) as response:
                if response.status in (400, 401):
                    raise AuthError("Invalid username or password")
                if response.status != 200:
                    raise ApiError(f"Login failed with HTTP {response.status}")
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(f"Login request failed: {err!r}") from err
        self._token = body["access_token"]

    async def async_get_user_id(self) -> int:
        """Return the id of the logged-in user."""
        body = await self._request("GET", "/api/profile")
        return int(body["data"]["id"])

    async def async_get_groups(self) -> list[DeviceGroup]:
        """Return all device groups with their units."""
        body = await self._request("GET", "/api/user-app/devicegroups")
        return [await self.async_get_group(item["id"]) for item in body["data"]]

    async def async_get_group(self, group_id: int) -> DeviceGroup:
        """Return one device group."""
        body = await self._request("GET", f"/api/user-app/devicegroups/{group_id}")
        return DeviceGroup.from_api(body)

    async def async_set_target_temperature(
        self, group_id: int, value: int
    ) -> DeviceGroup:
        """Set the target temperature of a group."""
        body = await self._request(
            "PUT",
            f"/api/user-app/devicegroups/{group_id}",
            {"target_temperature": value},
        )
        return DeviceGroup.from_api(body)

    async def async_set_pause_inlets(
        self, group_id: int, until: datetime | None
    ) -> DeviceGroup:
        """Pause the inlets until a time, or stop the pause with None."""
        value = (
            None
            if until is None
            else until.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        )
        body = await self._request(
            "PUT",
            f"/api/user-app/devicegroups/{group_id}",
            {"pause_inlets_until": value},
        )
        return DeviceGroup.from_api(body)

    async def async_set_comfort_level(
        self, group_id: int, unit_id: int, level: int
    ) -> None:
        """Set the comfort level (1-6) of one unit."""
        await self._request(
            "PATCH",
            f"/api/user-app/devicegroups/{group_id}/devices/{unit_id}",
            {"comfort_level": level},
        )

    async def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> Any:
        if self._token is None:
            await self.async_login()
        status, body = await self._send(method, path, json)
        if status == 401:
            await self.async_login()
            status, body = await self._send(method, path, json)
            if status == 401:
                raise AuthError("Token rejected after new login")
        if not 200 <= status < 300:
            raise ApiError(f"{method} {path} failed with HTTP {status}")
        return body

    async def _send(
        self, method: str, path: str, json: dict[str, Any] | None
    ) -> tuple[int, Any]:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        try:
            async with self._session.request(
                method, f"{BASE_URL}{path}", headers=headers, json=json, timeout=TIMEOUT
            ) as response:
                if not 200 <= response.status < 300:
                    return response.status, None
                return response.status, await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(f"{method} {path} failed: {err!r}") from err
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_api.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/airbynature/api.py tests/test_api.py
git commit -m "Add async AirByNature API client

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Coordinator, setup/unload, base entities, translations

**Files:**
- Create: `custom_components/airbynature/coordinator.py`, `custom_components/airbynature/entity.py`, `custom_components/airbynature/icons.json`
- Modify: `custom_components/airbynature/__init__.py` (replace whole file), `custom_components/airbynature/strings.json` (replace), `custom_components/airbynature/translations/en.json` (replace), `custom_components/airbynature/translations/da.json` (replace)
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: `AirByNatureClient`, `AirByNatureError`, `AuthError` (Task 2); `DeviceGroup`, `Unit` (Task 1).
- Produces:
  - `coordinator.AirByNatureConfigEntry` (= `ConfigEntry[AirByNatureCoordinator]`)
  - `AirByNatureCoordinator(hass, entry, client)` with `.client: AirByNatureClient`, `.data: dict[int, DeviceGroup]`, `@callback async_apply_group(group: DeviceGroup) -> None`
  - `__init__.PLATFORMS: list[Platform]` (empty here; each platform task appends)
  - `entity.group_device_info(group) -> DeviceInfo`, `entity.unit_device_info(group_id, unit) -> DeviceInfo`
  - `entity.call_api(request: Awaitable[T]) -> T` (raises `HomeAssistantError` with translation key `command_failed`)
  - `entity.AirByNatureGroupEntity(coordinator, group_id, key)` with `.group_id`, `.group`
  - `entity.AirByNatureUnitEntity(coordinator, group_id, unit_id, key)` with `.group_id`, `.unit_id`, `.unit`
  - Translation keys for every entity in the spec (used by Tasks 4–7), and config flow texts (used by Task 8).

- [ ] **Step 1: Write the failing tests**

`tests/test_init.py`:

```python
"""Tests for AirByNature setup and unload."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.api import AuthError, CannotConnect
from custom_components.airbynature.const import DOMAIN

from .helpers import setup_integration


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_group_device_registered(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "group_100")})

    assert device is not None
    assert device.name == "Testvej 1"
    assert device.manufacturer == "AirByNature"
    assert device.model == "Device group"


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_get_groups.side_effect = CannotConnect("boom")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_failure_fails_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_get_groups.side_effect = AuthError("rejected")

    await setup_integration(hass, mock_config_entry)

    # That a reauth flow starts is asserted in Task 8, once the config flow exists.
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_account_without_groups(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_get_groups.return_value = []

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass), mock_config_entry.entry_id
    )
    assert devices == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_init.py -v`
Expected: FAIL — `AttributeError: <module 'custom_components.airbynature'> does not have the attribute 'AirByNatureClient'` (from the `mock_client` patch).

- [ ] **Step 3: Implement the coordinator**

`custom_components/airbynature/coordinator.py`:

```python
"""Data update coordinator for AirByNature."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AirByNatureClient, AirByNatureError, AuthError
from .const import DOMAIN, UPDATE_INTERVAL
from .models import DeviceGroup

_LOGGER = logging.getLogger(__name__)

type AirByNatureConfigEntry = ConfigEntry[AirByNatureCoordinator]


class AirByNatureCoordinator(DataUpdateCoordinator[dict[int, DeviceGroup]]):
    """Polls all device groups of one account."""

    config_entry: AirByNatureConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AirByNatureConfigEntry,
        client: AirByNatureClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, DeviceGroup]:
        try:
            groups = await self.client.async_get_groups()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AirByNatureError as err:
            raise UpdateFailed(f"Error communicating with AirByNature: {err}") from err
        return {group.id: group for group in groups}

    @callback
    def async_apply_group(self, group: DeviceGroup) -> None:
        """Store a group returned by a command without polling again."""
        self.async_set_updated_data({**self.data, group.id: group})
```

- [ ] **Step 4: Implement the base entities**

`custom_components/airbynature/entity.py`:

```python
"""Base entities for AirByNature."""

from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AirByNatureError
from .const import DOMAIN, MANUFACTURER
from .coordinator import AirByNatureCoordinator
from .models import DeviceGroup, Unit


def group_device_info(group: DeviceGroup) -> DeviceInfo:
    """Device info for a device group."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"group_{group.id}")},
        name=group.display_name,
        manufacturer=MANUFACTURER,
        model="Device group",
    )


def unit_device_info(group_id: int, unit: Unit) -> DeviceInfo:
    """Device info for a unit, linked to its group."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"unit_{unit.id}")},
        name=unit.name or f"Unit {unit.id}",
        manufacturer=MANUFACTURER,
        model=unit.type,
        serial_number=unit.serial_number,
        via_device=(DOMAIN, f"group_{group_id}"),
    )


async def call_api[T](request: Awaitable[T]) -> T:
    """Await an API command, turning client errors into HomeAssistantError."""
    try:
        return await request
    except AirByNatureError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"error": str(err)},
        ) from err


class AirByNatureGroupEntity(CoordinatorEntity[AirByNatureCoordinator]):
    """Entity belonging to a device group."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AirByNatureCoordinator, group_id: int, key: str
    ) -> None:
        super().__init__(coordinator)
        self.group_id = group_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{group_id}_{key}"
        self._attr_device_info = group_device_info(coordinator.data[group_id])

    @property
    def group(self) -> DeviceGroup:
        """Current data for this entity's group."""
        return self.coordinator.data[self.group_id]

    @property
    def available(self) -> bool:
        return super().available and self.group_id in self.coordinator.data


class AirByNatureUnitEntity(CoordinatorEntity[AirByNatureCoordinator]):
    """Entity belonging to a unit."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        unit_id: int,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self.group_id = group_id
        self.unit_id = unit_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{unit_id}_{key}"
        self._attr_device_info = unit_device_info(
            group_id, coordinator.data[group_id].units[unit_id]
        )

    @property
    def unit(self) -> Unit:
        """Current data for this entity's unit."""
        return self.coordinator.data[self.group_id].units[self.unit_id]

    @property
    def available(self) -> bool:
        group = self.coordinator.data.get(self.group_id)
        return super().available and group is not None and self.unit_id in group.units
```

- [ ] **Step 5: Implement setup/unload**

`custom_components/airbynature/__init__.py` (whole file):

```python
"""The AirByNature integration."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AirByNatureClient
from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import group_device_info

PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: AirByNatureConfigEntry) -> bool:
    """Set up AirByNature from a config entry."""
    client = AirByNatureClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = AirByNatureCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register group devices first so unit devices can reference them via_device.
    device_registry = dr.async_get(hass)
    for group in coordinator.data.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **group_device_info(group)
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirByNatureConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

- [ ] **Step 6: Translations and icons**

`custom_components/airbynature/translations/en.json` (whole file):

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Sign in to AirByNature",
        "description": "Use the e-mail and password from the AirByNature app.",
        "data": {
          "username": "E-mail",
          "password": "Password"
        }
      },
      "reauth_confirm": {
        "title": "Re-authenticate AirByNature",
        "description": "The password for {username} is no longer valid. Enter the current password.",
        "data": {
          "password": "Password"
        }
      }
    },
    "error": {
      "invalid_auth": "Invalid e-mail or password.",
      "cannot_connect": "Cannot connect to the AirByNature service.",
      "unknown": "Unexpected error."
    },
    "abort": {
      "already_configured": "This AirByNature account is already configured.",
      "reauth_successful": "Re-authentication was successful.",
      "wrong_account": "The credentials belong to a different AirByNature account."
    }
  },
  "entity": {
    "sensor": {
      "avg_temperature": { "name": "Average temperature" },
      "mode": { "name": "Mode" },
      "current_rule": { "name": "Current rule" },
      "pause_inlets_until": { "name": "Inlets paused until" },
      "pause_until": { "name": "Paused until" },
      "status": { "name": "Status" },
      "inlet_temperature": { "name": "Inlet temperature" },
      "outlet_temperature": { "name": "Outlet temperature" },
      "external_temperature": { "name": "Outdoor temperature" },
      "inlet_humidity": { "name": "Inlet humidity" },
      "outlet_humidity": { "name": "Outlet humidity" },
      "co2": { "name": "CO2" },
      "tvoc": { "name": "TVOC" },
      "inlet_fan": { "name": "Inlet fan" },
      "outlet_fan": { "name": "Outlet fan" },
      "inlet_fan1_rpm": { "name": "Inlet fan 1 speed" },
      "outlet_fan1_rpm": { "name": "Outlet fan 1 speed" },
      "inlet_fan2_rpm": { "name": "Inlet fan 2 speed" },
      "outlet_fan2_rpm": { "name": "Outlet fan 2 speed" },
      "last_measurement": { "name": "Last measurement" },
      "wifi_signal": { "name": "Wi-Fi signal" },
      "inlet_speed_factor": { "name": "Inlet speed factor" },
      "outlet_speed_factor": { "name": "Outlet speed factor" },
      "interval": { "name": "Measurement interval" }
    },
    "binary_sensor": {
      "rule_enabled": { "name": "Rule enabled" },
      "drying": { "name": "Drying" },
      "online": { "name": "Online" },
      "filter": { "name": "Filter" },
      "drying_heat_exchanger": { "name": "Drying heat exchanger" }
    },
    "number": {
      "target_temperature": { "name": "Target temperature" },
      "pause_inlets": { "name": "Pause inlets" }
    },
    "select": {
      "comfort_level": {
        "name": "Comfort level",
        "state": {
          "off": "Off",
          "very_quiet": "Very quiet",
          "quiet": "Quiet",
          "normal": "Normal",
          "high": "High",
          "extra_high": "Extra high"
        }
      }
    }
  },
  "exceptions": {
    "command_failed": {
      "message": "AirByNature rejected the command: {error}"
    }
  }
}
```

Copy it to `strings.json`:

```bash
cp custom_components/airbynature/translations/en.json custom_components/airbynature/strings.json
```

`custom_components/airbynature/translations/da.json` (whole file):

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Log ind på AirByNature",
        "description": "Brug e-mail og adgangskode fra AirByNature-appen.",
        "data": {
          "username": "E-mail",
          "password": "Adgangskode"
        }
      },
      "reauth_confirm": {
        "title": "Log ind på AirByNature igen",
        "description": "Adgangskoden for {username} er ikke længere gyldig. Indtast den nuværende adgangskode.",
        "data": {
          "password": "Adgangskode"
        }
      }
    },
    "error": {
      "invalid_auth": "Forkert e-mail eller adgangskode.",
      "cannot_connect": "Kan ikke forbinde til AirByNature.",
      "unknown": "Uventet fejl."
    },
    "abort": {
      "already_configured": "Denne AirByNature-konto er allerede konfigureret.",
      "reauth_successful": "Du er logget ind igen.",
      "wrong_account": "Loginoplysningerne tilhører en anden AirByNature-konto."
    }
  },
  "entity": {
    "sensor": {
      "avg_temperature": { "name": "Gennemsnitstemperatur" },
      "mode": { "name": "Tilstand" },
      "current_rule": { "name": "Aktiv regel" },
      "pause_inlets_until": { "name": "Indblæsning pauset til" },
      "pause_until": { "name": "Pauset til" },
      "status": { "name": "Status" },
      "inlet_temperature": { "name": "Indblæsningstemperatur" },
      "outlet_temperature": { "name": "Udsugningstemperatur" },
      "external_temperature": { "name": "Udetemperatur" },
      "inlet_humidity": { "name": "Indblæsningsfugtighed" },
      "outlet_humidity": { "name": "Udsugningsfugtighed" },
      "co2": { "name": "CO2" },
      "tvoc": { "name": "TVOC" },
      "inlet_fan": { "name": "Indblæsningsventilator" },
      "outlet_fan": { "name": "Udsugningsventilator" },
      "inlet_fan1_rpm": { "name": "Indblæsningsventilator 1 hastighed" },
      "outlet_fan1_rpm": { "name": "Udsugningsventilator 1 hastighed" },
      "inlet_fan2_rpm": { "name": "Indblæsningsventilator 2 hastighed" },
      "outlet_fan2_rpm": { "name": "Udsugningsventilator 2 hastighed" },
      "last_measurement": { "name": "Seneste måling" },
      "wifi_signal": { "name": "Wi-Fi-signal" },
      "inlet_speed_factor": { "name": "Indblæsningshastighedsfaktor" },
      "outlet_speed_factor": { "name": "Udsugningshastighedsfaktor" },
      "interval": { "name": "Måleinterval" }
    },
    "binary_sensor": {
      "rule_enabled": { "name": "Regel aktiveret" },
      "drying": { "name": "Tørring" },
      "online": { "name": "Online" },
      "filter": { "name": "Filter" },
      "drying_heat_exchanger": { "name": "Tørrer varmeveksler" }
    },
    "number": {
      "target_temperature": { "name": "Måltemperatur" },
      "pause_inlets": { "name": "Pause indblæsning" }
    },
    "select": {
      "comfort_level": {
        "name": "Komfortniveau",
        "state": {
          "off": "Slukket",
          "very_quiet": "Meget stille",
          "quiet": "Stille",
          "normal": "Normal",
          "high": "Høj",
          "extra_high": "Ekstra høj"
        }
      }
    }
  },
  "exceptions": {
    "command_failed": {
      "message": "AirByNature afviste kommandoen: {error}"
    }
  }
}
```

`custom_components/airbynature/icons.json`:

```json
{
  "entity": {
    "sensor": {
      "mode": { "default": "mdi:tune" },
      "current_rule": { "default": "mdi:script-text-outline" },
      "pause_inlets_until": { "default": "mdi:pause-circle-outline" },
      "pause_until": { "default": "mdi:pause-circle-outline" },
      "status": { "default": "mdi:information-outline" },
      "inlet_fan": { "default": "mdi:fan" },
      "outlet_fan": { "default": "mdi:fan" },
      "inlet_fan1_rpm": { "default": "mdi:fan" },
      "outlet_fan1_rpm": { "default": "mdi:fan" },
      "inlet_fan2_rpm": { "default": "mdi:fan" },
      "outlet_fan2_rpm": { "default": "mdi:fan" },
      "wifi_signal": { "default": "mdi:wifi" },
      "inlet_speed_factor": { "default": "mdi:speedometer" },
      "outlet_speed_factor": { "default": "mdi:speedometer" }
    },
    "binary_sensor": {
      "rule_enabled": { "default": "mdi:script-text-outline" },
      "drying": { "default": "mdi:water-off-outline" },
      "filter": { "default": "mdi:air-filter" },
      "drying_heat_exchanger": { "default": "mdi:heat-wave" }
    },
    "number": {
      "pause_inlets": { "default": "mdi:pause-circle-outline" }
    },
    "select": {
      "comfort_level": {
        "default": "mdi:fan",
        "state": { "off": "mdi:fan-off" }
      }
    }
  }
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_init.py -v && for f in custom_components/airbynature/*.json custom_components/airbynature/translations/*.json; do python3 -m json.tool "$f" > /dev/null || echo "INVALID $f"; done`
Expected: all tests PASS, no `INVALID` lines.

- [ ] **Step 8: Commit**

```bash
git add custom_components/airbynature/__init__.py custom_components/airbynature/coordinator.py custom_components/airbynature/entity.py custom_components/airbynature/strings.json custom_components/airbynature/icons.json custom_components/airbynature/translations/en.json custom_components/airbynature/translations/da.json tests/test_init.py
git commit -m "Add coordinator, entry setup, base entities and translations

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Sensor platform

**Files:**
- Create: `custom_components/airbynature/sensor.py`
- Modify: `custom_components/airbynature/__init__.py` (`PLATFORMS`)
- Test: `tests/test_sensor.py`

**Interfaces:**
- Consumes: `AirByNatureGroupEntity`, `AirByNatureUnitEntity` (`.group`, `.unit`), `AirByNatureConfigEntry`, `AirByNatureCoordinator` (Task 3); `DeviceGroup`, `Unit` (Task 1).
- Produces: `GROUP_SENSORS`, `UNIT_SENSORS` tuples (keys exactly as in the spec tables).

- [ ] **Step 1: Write the failing tests**

`tests/test_sensor.py`:

```python
"""Tests for AirByNature sensors."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.const import DOMAIN
from custom_components.airbynature.models import DeviceGroup

from .helpers import entity_id, setup_integration


@pytest.mark.parametrize(
    ("unique_id", "expected"),
    [
        ("100_avg_temperature", "25.9"),
        ("100_mode", "comfort"),
        ("100_current_rule", "Svale 1 - Fugt 1 (>55%)"),
        ("100_pause_inlets_until", STATE_UNKNOWN),
        ("100_status", "ok"),
        ("200_inlet_temperature", "23.89"),
        ("200_outlet_temperature", "25.9"),
        ("200_external_temperature", "24.97"),
        ("200_inlet_humidity", "60.3"),
        ("200_outlet_humidity", "55.3"),
        ("200_co2", "440.3"),
        ("200_tvoc", "46.9"),
        ("200_inlet_fan", "0"),
        ("200_outlet_fan", "74"),
        ("200_inlet_fan1_rpm", "0"),
        ("200_outlet_fan1_rpm", "3617"),
        ("200_last_measurement", "2024-09-24T16:00:28+00:00"),
        ("200_wifi_signal", "28"),
        ("200_inlet_speed_factor", "55.0"),
        ("200_outlet_speed_factor", "65.0"),
        ("200_interval", "60"),
    ],
)
async def test_sensor_values(
    hass: HomeAssistant, init_integration: MockConfigEntry, unique_id: str, expected: str
) -> None:
    state = hass.states.get(entity_id(hass, "sensor", unique_id))

    assert state is not None
    assert state.state == expected


async def test_sensor_units(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    def unit(unique_id: str) -> str | None:
        return hass.states.get(entity_id(hass, "sensor", unique_id)).attributes.get(
            "unit_of_measurement"
        )

    assert unit("100_avg_temperature") == "°C"
    assert unit("200_inlet_humidity") == "%"
    assert unit("200_co2") == "ppm"
    assert unit("200_tvoc") == "ppb"
    assert unit("200_outlet_fan1_rpm") == "rpm"
    assert unit("200_outlet_fan") == "%"
    assert unit("200_wifi_signal") is None


async def test_fan2_sensors_disabled_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    registry = er.async_get(hass)
    for key in ("200_inlet_fan2_rpm", "200_outlet_fan2_rpm", "100_pause_until"):
        entry = registry.async_get(entity_id(hass, "sensor", key))
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_diagnostic_category(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id(hass, "sensor", "200_wifi_signal"))
    assert entry.entity_category == "diagnostic"


async def test_device_tree(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    registry = dr.async_get(hass)
    group = registry.async_get_device(identifiers={(DOMAIN, "group_100")})
    unit = registry.async_get_device(identifiers={(DOMAIN, "unit_200")})

    assert unit is not None
    assert unit.name == "Loftanlæg"
    assert unit.model == "main-v2"
    assert unit.via_device_id == group.id

    sensor = er.async_get(hass).async_get(entity_id(hass, "sensor", "200_co2"))
    assert sensor.device_id == unit.id


async def test_multiple_groups(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    first = DeviceGroup.from_api(group_payload)
    group_payload["data"]["id"] = 101
    group_payload["data"]["address"] = "Andenvej 2"
    group_payload["data"]["devices"][0]["id"] = 201
    group_payload["data"]["devices"][0]["latest_history"]["outlet_co2"] = 999.0
    mock_client.async_get_groups.return_value = [first, DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == "440.3"
    assert hass.states.get(entity_id(hass, "sensor", "201_co2")).state == "999.0"
    unit = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "unit_201")})
    group = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "group_101")})
    assert group.name == "Andenvej 2"
    assert unit.via_device_id == group.id


async def test_offline_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"][0]["is_online"] = False
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_id(hass, "sensor", "200_wifi_signal")).state == "28"
    assert hass.states.get(entity_id(hass, "sensor", "100_avg_temperature")).state == "25.9"


async def test_unit_without_history(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"][0]["latest_history"] = None
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == STATE_UNKNOWN
    assert (
        hass.states.get(entity_id(hass, "sensor", "200_last_measurement")).state
        == STATE_UNKNOWN
    )


async def test_unknown_mode_is_shown_verbatim(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["mode"] = "away"
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "sensor", "100_mode")).state == "away"


async def test_values_follow_updates(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"][0]["latest_history"]["outlet_co2"] = 612.5
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == "612.5"


async def test_removed_unit_becomes_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"] = []
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id(hass, "sensor", "200_co2")).state == STATE_UNAVAILABLE
    assert hass.states.get(entity_id(hass, "sensor", "100_avg_temperature")).state == "25.9"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sensor.py -v`
Expected: FAIL — `AssertionError: no sensor entity with unique_id ...`.

- [ ] **Step 3: Implement `sensor.py`**

`custom_components/airbynature/sensor.py`:

```python
"""Sensor platform for AirByNature."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import AirByNatureGroupEntity, AirByNatureUnitEntity
from .models import DeviceGroup, Unit

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirByNatureGroupSensorDescription(SensorEntityDescription):
    """Describes a device group sensor."""

    value_fn: Callable[[DeviceGroup], StateType | datetime]


@dataclass(frozen=True, kw_only=True)
class AirByNatureUnitSensorDescription(SensorEntityDescription):
    """Describes a unit sensor."""

    value_fn: Callable[[Unit], StateType | datetime]
    requires_online: bool = True


def _temperature(
    key: str, value_fn: Callable[[Unit], StateType]
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=value_fn,
    )


def _humidity(
    key: str, value_fn: Callable[[Unit], StateType]
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=value_fn,
    )


def _fan_percent(
    key: str, value_fn: Callable[[Unit], StateType]
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=value_fn,
    )


def _rpm(
    key: str, value_fn: Callable[[Unit], StateType], *, enabled: bool = True
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
        value_fn=value_fn,
    )


def _speed_factor(
    key: str, value_fn: Callable[[Unit], StateType]
) -> AirByNatureUnitSensorDescription:
    return AirByNatureUnitSensorDescription(
        key=key,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        value_fn=value_fn,
    )


GROUP_SENSORS: tuple[AirByNatureGroupSensorDescription, ...] = (
    AirByNatureGroupSensorDescription(
        key="avg_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda group: group.avg_temp,
    ),
    AirByNatureGroupSensorDescription(
        key="mode",
        value_fn=lambda group: group.mode,
    ),
    AirByNatureGroupSensorDescription(
        key="current_rule",
        value_fn=lambda group: group.current_running_rule,
    ),
    AirByNatureGroupSensorDescription(
        key="pause_inlets_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda group: group.pause_inlets_until,
    ),
    AirByNatureGroupSensorDescription(
        key="pause_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda group: group.pause_until,
    ),
    AirByNatureGroupSensorDescription(
        key="status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda group: group.status,
    ),
)

UNIT_SENSORS: tuple[AirByNatureUnitSensorDescription, ...] = (
    _temperature("inlet_temperature", lambda unit: unit.measurements.inlet_temp),
    _temperature("outlet_temperature", lambda unit: unit.measurements.outlet_temp),
    _temperature("external_temperature", lambda unit: unit.measurements.external_temp),
    _humidity("inlet_humidity", lambda unit: unit.measurements.inlet_humid),
    _humidity("outlet_humidity", lambda unit: unit.measurements.outlet_humid),
    AirByNatureUnitSensorDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda unit: unit.measurements.outlet_co2,
    ),
    AirByNatureUnitSensorDescription(
        key="tvoc",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_BILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda unit: unit.measurements.outlet_tvoc,
    ),
    _fan_percent("inlet_fan", lambda unit: unit.measurements.inlet_fan),
    _fan_percent("outlet_fan", lambda unit: unit.measurements.outlet_fan),
    _rpm("inlet_fan1_rpm", lambda unit: unit.measurements.inlet_fan1_rpm),
    _rpm("outlet_fan1_rpm", lambda unit: unit.measurements.outlet_fan1_rpm),
    _rpm("inlet_fan2_rpm", lambda unit: unit.measurements.inlet_fan2_rpm, enabled=False),
    _rpm(
        "outlet_fan2_rpm", lambda unit: unit.measurements.outlet_fan2_rpm, enabled=False
    ),
    AirByNatureUnitSensorDescription(
        key="last_measurement",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        value_fn=lambda unit: unit.measurements.measured_at,
    ),
    AirByNatureUnitSensorDescription(
        key="wifi_signal",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        value_fn=lambda unit: unit.wifi_signal,
    ),
    _speed_factor("inlet_speed_factor", lambda unit: unit.inlet_speed_factor),
    _speed_factor("outlet_speed_factor", lambda unit: unit.outlet_speed_factor),
    AirByNatureUnitSensorDescription(
        key="interval",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        requires_online=False,
        value_fn=lambda unit: unit.current_interval,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirByNatureConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirByNature sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for group_id, group in coordinator.data.items():
        entities.extend(
            AirByNatureGroupSensor(coordinator, group_id, description)
            for description in GROUP_SENSORS
        )
        for unit_id in group.units:
            entities.extend(
                AirByNatureUnitSensor(coordinator, group_id, unit_id, description)
                for description in UNIT_SENSORS
            )
    async_add_entities(entities)


class AirByNatureGroupSensor(AirByNatureGroupEntity, SensorEntity):
    """Sensor for a device group value."""

    entity_description: AirByNatureGroupSensorDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        description: AirByNatureGroupSensorDescription,
    ) -> None:
        super().__init__(coordinator, group_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.group)


class AirByNatureUnitSensor(AirByNatureUnitEntity, SensorEntity):
    """Sensor for a unit value."""

    entity_description: AirByNatureUnitSensorDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        unit_id: int,
        description: AirByNatureUnitSensorDescription,
    ) -> None:
        super().__init__(coordinator, group_id, unit_id, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self.unit.is_online or not self.entity_description.requires_online

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.unit)
```

In `custom_components/airbynature/__init__.py` change:

```python
PLATFORMS: list[Platform] = []
```

to:

```python
PLATFORMS: list[Platform] = [Platform.SENSOR]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_sensor.py tests/test_init.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/airbynature/sensor.py custom_components/airbynature/__init__.py tests/test_sensor.py
git commit -m "Add sensor platform for groups and units

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Binary sensor platform

**Files:**
- Create: `custom_components/airbynature/binary_sensor.py`
- Modify: `custom_components/airbynature/__init__.py` (`PLATFORMS`)
- Test: `tests/test_binary_sensor.py`

**Interfaces:**
- Consumes: `AirByNatureGroupEntity`, `AirByNatureUnitEntity`, `AirByNatureConfigEntry`, `AirByNatureCoordinator` (Task 3).
- Produces: `GROUP_BINARY_SENSORS`, `UNIT_BINARY_SENSORS`.

- [ ] **Step 1: Write the failing tests**

`tests/test_binary_sensor.py`:

```python
"""Tests for AirByNature binary sensors."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.models import DeviceGroup

from .helpers import entity_id, setup_integration


@pytest.mark.parametrize(
    ("unique_id", "expected"),
    [
        ("100_rule_enabled", STATE_ON),
        ("100_drying", STATE_OFF),
        ("200_online", STATE_ON),
        ("200_filter", STATE_ON),
        ("200_drying_heat_exchanger", STATE_OFF),
    ],
)
async def test_binary_sensor_values(
    hass: HomeAssistant, init_integration: MockConfigEntry, unique_id: str, expected: str
) -> None:
    state = hass.states.get(entity_id(hass, "binary_sensor", unique_id))

    assert state is not None
    assert state.state == expected


async def test_online_device_class(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(entity_id(hass, "binary_sensor", "200_online"))

    assert state.attributes["device_class"] == "connectivity"


async def test_offline_unit_reports_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["devices"][0]["is_online"] = False
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id(hass, "binary_sensor", "200_online")).state == STATE_OFF
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_binary_sensor.py -v`
Expected: FAIL — `AssertionError: no binary_sensor entity with unique_id ...`.

- [ ] **Step 3: Implement `binary_sensor.py`**

`custom_components/airbynature/binary_sensor.py`:

```python
"""Binary sensor platform for AirByNature."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import AirByNatureGroupEntity, AirByNatureUnitEntity
from .models import DeviceGroup, Unit

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirByNatureGroupBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a device group binary sensor."""

    value_fn: Callable[[DeviceGroup], bool | None]


@dataclass(frozen=True, kw_only=True)
class AirByNatureUnitBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a unit binary sensor."""

    value_fn: Callable[[Unit], bool | None]


GROUP_BINARY_SENSORS: tuple[AirByNatureGroupBinarySensorDescription, ...] = (
    AirByNatureGroupBinarySensorDescription(
        key="rule_enabled",
        value_fn=lambda group: group.is_rule_enabled,
    ),
    AirByNatureGroupBinarySensorDescription(
        key="drying",
        value_fn=lambda group: group.is_drying,
    ),
)

UNIT_BINARY_SENSORS: tuple[AirByNatureUnitBinarySensorDescription, ...] = (
    AirByNatureUnitBinarySensorDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.is_online,
    ),
    AirByNatureUnitBinarySensorDescription(
        key="filter",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.has_filter,
    ),
    AirByNatureUnitBinarySensorDescription(
        key="drying_heat_exchanger",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda unit: unit.is_drying_heat_exchanger,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirByNatureConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirByNature binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for group_id, group in coordinator.data.items():
        entities.extend(
            AirByNatureGroupBinarySensor(coordinator, group_id, description)
            for description in GROUP_BINARY_SENSORS
        )
        for unit_id in group.units:
            entities.extend(
                AirByNatureUnitBinarySensor(coordinator, group_id, unit_id, description)
                for description in UNIT_BINARY_SENSORS
            )
    async_add_entities(entities)


class AirByNatureGroupBinarySensor(AirByNatureGroupEntity, BinarySensorEntity):
    """Binary sensor for a device group value."""

    entity_description: AirByNatureGroupBinarySensorDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        description: AirByNatureGroupBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, group_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.group)


class AirByNatureUnitBinarySensor(AirByNatureUnitEntity, BinarySensorEntity):
    """Binary sensor for a unit value (stays available while the unit is offline)."""

    entity_description: AirByNatureUnitBinarySensorDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        unit_id: int,
        description: AirByNatureUnitBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, group_id, unit_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.unit)
```

In `custom_components/airbynature/__init__.py` change:

```python
PLATFORMS: list[Platform] = [Platform.SENSOR]
```

to:

```python
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_binary_sensor.py tests/test_sensor.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/airbynature/binary_sensor.py custom_components/airbynature/__init__.py tests/test_binary_sensor.py
git commit -m "Add binary sensor platform

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Number platform (target temperature, pause inlets)

**Files:**
- Create: `custom_components/airbynature/number.py`
- Modify: `custom_components/airbynature/__init__.py` (`PLATFORMS`)
- Test: `tests/test_number.py`

**Interfaces:**
- Consumes: `AirByNatureGroupEntity`, `call_api`, `AirByNatureCoordinator.async_apply_group`, `.client` (Task 3); `AirByNatureClient.async_set_target_temperature(group_id, value)`, `async_set_pause_inlets(group_id, until)` (Task 2); `Permissions` (Task 1).
- Produces: `number.remaining_hours(until: datetime | None, now: datetime) -> int`, `number._utcnow() -> datetime` (patch point for tests).

- [ ] **Step 1: Write the failing tests**

`tests/test_number.py`:

```python
"""Tests for AirByNature number entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.api import ApiError
from custom_components.airbynature.const import DOMAIN
from custom_components.airbynature.models import DeviceGroup
from custom_components.airbynature.number import remaining_hours

from .helpers import entity_id, setup_integration

NOW = datetime(2024, 9, 24, 16, 0, tzinfo=UTC)


async def _set_value(hass: HomeAssistant, entity: str, value: float) -> None:
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity, ATTR_VALUE: value},
        blocking=True,
    )


@pytest.mark.parametrize(
    ("until", "expected"),
    [
        (None, 0),
        (NOW - timedelta(minutes=1), 0),
        (NOW, 0),
        (NOW + timedelta(minutes=1), 1),
        (NOW + timedelta(minutes=90), 2),
        (NOW + timedelta(hours=30), 30),
    ],
)
def test_remaining_hours(until: datetime | None, expected: int) -> None:
    assert remaining_hours(until, NOW) == expected


async def test_target_temperature_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(entity_id(hass, "number", "100_target_temperature"))

    assert float(state.state) == 23
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 40
    assert state.attributes["step"] == 1
    assert state.attributes["unit_of_measurement"] == "°C"


async def test_set_target_temperature(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["data"]["target_temperature"] = 21
    mock_client.async_set_target_temperature.return_value = DeviceGroup.from_api(
        group_payload
    )
    entity = entity_id(hass, "number", "100_target_temperature")

    await _set_value(hass, entity, 21)

    mock_client.async_set_target_temperature.assert_awaited_once_with(100, 21)
    assert float(hass.states.get(entity).state) == 21
    # Updated from the PUT response, not from an extra poll.
    assert mock_client.async_get_groups.await_count == 1


async def test_pause_inlets_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    until = dt_util.utcnow() + timedelta(minutes=90)
    group_payload["data"]["pause_inlets_until"] = until.isoformat()
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id(hass, "number", "100_pause_inlets"))
    assert float(state.state) == 2
    assert state.attributes["max"] == 24


async def test_pause_longer_than_max(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    until = dt_util.utcnow() + timedelta(hours=30)
    group_payload["data"]["pause_inlets_until"] = until.isoformat()
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id(hass, "number", "100_pause_inlets"))
    assert float(state.state) == 30


async def test_not_paused_shows_zero(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(entity_id(hass, "number", "100_pause_inlets"))

    assert float(state.state) == 0


async def test_set_pause_inlets(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    entity = entity_id(hass, "number", "100_pause_inlets")

    with patch("custom_components.airbynature.number._utcnow", return_value=NOW):
        await _set_value(hass, entity, 2)

    mock_client.async_set_pause_inlets.assert_awaited_once_with(
        100, NOW + timedelta(hours=2)
    )


async def test_stop_pause_inlets(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    entity = entity_id(hass, "number", "100_pause_inlets")

    await _set_value(hass, entity, 0)

    mock_client.async_set_pause_inlets.assert_awaited_once_with(100, None)


async def test_command_failure_raises(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_set_target_temperature.side_effect = ApiError("HTTP 500")
    entity = entity_id(hass, "number", "100_target_temperature")

    with pytest.raises(HomeAssistantError):
        await _set_value(hass, entity, 20)


async def test_controls_hidden_without_permission(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["meta"]["permissions"]["canChangeTemperature"] = False
    group_payload["meta"]["permissions"]["canPauseInlets"] = False
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("number", DOMAIN, "100_target_temperature") is None
    assert registry.async_get_entity_id("number", DOMAIN, "100_pause_inlets") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_number.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'custom_components.airbynature.number'`.

- [ ] **Step 3: Implement `number.py`**

`custom_components/airbynature/number.py`:

```python
"""Number platform for AirByNature."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import AirByNatureClient
from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import AirByNatureGroupEntity, call_api
from .models import DeviceGroup, Permissions

PARALLEL_UPDATES = 1


def _utcnow() -> datetime:
    return dt_util.utcnow()


def remaining_hours(until: datetime | None, now: datetime) -> int:
    """Whole hours left until ``until``, rounded up; 0 when not in the future."""
    if until is None or until <= now:
        return 0
    return math.ceil((until - now).total_seconds() / 3600)


def _pause_until(hours: int) -> datetime | None:
    return _utcnow() + timedelta(hours=hours) if hours > 0 else None


@dataclass(frozen=True, kw_only=True)
class AirByNatureNumberDescription(NumberEntityDescription):
    """Describes a device group number."""

    permission_fn: Callable[[Permissions], bool]
    value_fn: Callable[[DeviceGroup], float | None]
    set_fn: Callable[[AirByNatureClient, int, int], Awaitable[DeviceGroup]]


NUMBERS: tuple[AirByNatureNumberDescription, ...] = (
    AirByNatureNumberDescription(
        key="target_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0,
        native_max_value=40,
        native_step=1,
        permission_fn=lambda permissions: permissions.can_change_temperature,
        value_fn=lambda group: group.target_temperature,
        set_fn=lambda client, group_id, value: client.async_set_target_temperature(
            group_id, value
        ),
    ),
    AirByNatureNumberDescription(
        key="pause_inlets",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=0,
        native_max_value=24,
        native_step=1,
        permission_fn=lambda permissions: permissions.can_pause_inlets,
        value_fn=lambda group: remaining_hours(group.pause_inlets_until, _utcnow()),
        set_fn=lambda client, group_id, value: client.async_set_pause_inlets(
            group_id, _pause_until(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirByNatureConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirByNature numbers."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirByNatureNumber(coordinator, group_id, description)
        for group_id, group in coordinator.data.items()
        for description in NUMBERS
        if description.permission_fn(group.permissions)
    )


class AirByNatureNumber(AirByNatureGroupEntity, NumberEntity):
    """Number controlling a device group setting."""

    entity_description: AirByNatureNumberDescription

    def __init__(
        self,
        coordinator: AirByNatureCoordinator,
        group_id: int,
        description: AirByNatureNumberDescription,
    ) -> None:
        super().__init__(coordinator, group_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.group)

    async def async_set_native_value(self, value: float) -> None:
        group = await call_api(
            self.entity_description.set_fn(
                self.coordinator.client, self.group_id, int(value)
            )
        )
        self.coordinator.async_apply_group(group)
```

In `custom_components/airbynature/__init__.py` change:

```python
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
```

to:

```python
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SENSOR]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_number.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/airbynature/number.py custom_components/airbynature/__init__.py tests/test_number.py
git commit -m "Add target temperature and pause inlets controls

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Select platform (comfort level)

**Files:**
- Create: `custom_components/airbynature/select.py`
- Modify: `custom_components/airbynature/__init__.py` (`PLATFORMS`)
- Test: `tests/test_select.py`

**Interfaces:**
- Consumes: `AirByNatureUnitEntity`, `call_api`, coordinator `.client` and `async_request_refresh()` (Task 3); `AirByNatureClient.async_set_comfort_level(group_id, unit_id, level)` (Task 2).
- Produces: `select.COMFORT_LEVELS: list[str]` (index + 1 = API level).

- [ ] **Step 1: Write the failing tests**

`tests/test_select.py`:

```python
"""Tests for AirByNature select entities."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbynature.api import CannotConnect
from custom_components.airbynature.const import DOMAIN
from custom_components.airbynature.models import DeviceGroup

from .helpers import entity_id, setup_integration


async def _select(hass: HomeAssistant, entity: str, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity, ATTR_OPTION: option},
        blocking=True,
    )


async def test_comfort_level_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(entity_id(hass, "select", "200_comfort_level"))

    assert state.state == "quiet"
    assert state.attributes["options"] == [
        "off",
        "very_quiet",
        "quiet",
        "normal",
        "high",
        "extra_high",
    ]


async def test_select_comfort_level(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    entity = entity_id(hass, "select", "200_comfort_level")

    await _select(hass, entity, "high")
    await hass.async_block_till_done()

    mock_client.async_set_comfort_level.assert_awaited_once_with(100, 200, 5)
    assert mock_client.async_get_groups.await_count == 2


async def test_select_off_sends_level_one(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    await _select(hass, entity_id(hass, "select", "200_comfort_level"), "off")

    mock_client.async_set_comfort_level.assert_awaited_once_with(100, 200, 1)


@pytest.mark.parametrize("level", [None, 0, 7])
async def test_comfort_level_out_of_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
    level: int | None,
) -> None:
    group_payload["data"]["devices"][0]["comfort_level"] = level
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id(hass, "select", "200_comfort_level"))
    assert state.state == STATE_UNKNOWN


async def test_command_failure_raises(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_client: MagicMock
) -> None:
    mock_client.async_set_comfort_level.side_effect = CannotConnect("timeout")

    with pytest.raises(HomeAssistantError):
        await _select(hass, entity_id(hass, "select", "200_comfort_level"), "normal")


async def test_hidden_without_permission(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    group_payload: dict[str, Any],
) -> None:
    group_payload["meta"]["permissions"]["canChangeAirCirculationLevel"] = False
    mock_client.async_get_groups.return_value = [DeviceGroup.from_api(group_payload)]

    await setup_integration(hass, mock_config_entry)

    assert (
        er.async_get(hass).async_get_entity_id("select", DOMAIN, "200_comfort_level")
        is None
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_select.py -v`
Expected: FAIL — `AssertionError: no select entity with unique_id 200_comfort_level`.

- [ ] **Step 3: Implement `select.py`**

`custom_components/airbynature/select.py`:

```python
"""Select platform for AirByNature."""

from __future__ import annotations

from typing import Final

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import AirByNatureConfigEntry, AirByNatureCoordinator
from .entity import AirByNatureUnitEntity, call_api

PARALLEL_UPDATES = 1

# Position + 1 is the API comfort level (1 = off ... 6 = extra high).
COMFORT_LEVELS: Final = ["off", "very_quiet", "quiet", "normal", "high", "extra_high"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirByNatureConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirByNature selects."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirByNatureComfortLevelSelect(coordinator, group_id, unit_id)
        for group_id, group in coordinator.data.items()
        if group.permissions.can_change_comfort_level
        for unit_id in group.units
    )


class AirByNatureComfortLevelSelect(AirByNatureUnitEntity, SelectEntity):
    """Comfort level (fan speed) of one unit."""

    _attr_options = COMFORT_LEVELS

    def __init__(
        self, coordinator: AirByNatureCoordinator, group_id: int, unit_id: int
    ) -> None:
        super().__init__(coordinator, group_id, unit_id, "comfort_level")

    @property
    def current_option(self) -> str | None:
        level = self.unit.comfort_level
        if level is None or not 1 <= level <= len(COMFORT_LEVELS):
            return None
        return COMFORT_LEVELS[level - 1]

    async def async_select_option(self, option: str) -> None:
        await call_api(
            self.coordinator.client.async_set_comfort_level(
                self.group_id, self.unit_id, COMFORT_LEVELS.index(option) + 1
            )
        )
        await self.coordinator.async_request_refresh()
```

In `custom_components/airbynature/__init__.py` change:

```python
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SENSOR]
```

to:

```python
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_select.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/airbynature/select.py custom_components/airbynature/__init__.py tests/test_select.py
git commit -m "Add comfort level select per unit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Config flow (user + reauth)

**Files:**
- Create: `custom_components/airbynature/config_flow.py`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `AirByNatureClient.async_login()`, `async_get_user_id()`, `AuthError`, `AirByNatureError` (Task 2); config texts in translations (Task 3); fixtures `mock_flow_client`, `mock_setup_entry`, `mock_config_entry` (Task 1).
- Produces: `AirByNatureConfigFlow` with steps `user`, `reauth`, `reauth_confirm`; config entry `unique_id = str(user_id)`, `title = username`, `data = {username, password}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_config_flow.py`:

```python
"""Tests for the AirByNature config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.config_entries import SOURCE_USER
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

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
    assert flows[0]["step_id"] == "reauth_confirm"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_config_flow.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'config_flow'` (from the `mock_flow_client` patch) or flow `unknown_handler`.

- [ ] **Step 3: Implement `config_flow.py`**

`custom_components/airbynature/config_flow.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_config_flow.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/airbynature/config_flow.py tests/test_config_flow.py
git commit -m "Add config flow with re-authentication

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Diagnostics

**Files:**
- Create: `custom_components/airbynature/diagnostics.py`
- Test: `tests/test_diagnostics.py`

**Interfaces:**
- Consumes: `AirByNatureConfigEntry`, coordinator `.data` (Task 3).
- Produces: `async_get_config_entry_diagnostics(hass, entry) -> dict[str, Any]` with keys `entry` and `groups`.

- [ ] **Step 1: Write the failing test**

`tests/test_diagnostics.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_diagnostics.py -v`
Expected: collection error `ModuleNotFoundError: No module named 'custom_components.airbynature.diagnostics'`.

- [ ] **Step 3: Implement `diagnostics.py`**

`custom_components/airbynature/diagnostics.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_diagnostics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add custom_components/airbynature/diagnostics.py tests/test_diagnostics.py
git commit -m "Add redacted diagnostics

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: HACS metadata, CI, README, final verification

**Files:**
- Modify: `hacs.json`, `README.md`
- Create: `.github/workflows/hassfest.yml`, `.github/workflows/hacs.yml`, `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: everything above.
- Produces: a branch ready for review and a manual test in Home Assistant.

- [ ] **Step 1: HACS metadata**

`hacs.json` (whole file):

```json
{
  "name": "AirByNature",
  "render_readme": true,
  "homeassistant": "2025.1.0"
}
```

- [ ] **Step 2: CI workflows**

`.github/workflows/hassfest.yml`:

```yaml
name: Validate with hassfest

on:
  push:
  pull_request:

jobs:
  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master
```

`.github/workflows/hacs.yml`:

```yaml
name: HACS validation

on:
  push:
  pull_request:

jobs:
  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: hacs/action@main
        with:
          category: integration
          # Brand icon is a follow-up PR to home-assistant/brands.
          ignore: brands
```

`.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  push:
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r requirements_test.txt
      - run: pytest
```

- [ ] **Step 3: README**

`README.md` (whole file):

```markdown
# AirByNature

Home Assistant integration for AirByNature ventilation systems, using the
AirByNature cloud (the same account as the AirByNature app).

## Installation

1. In HACS, open **Integrations → ⋮ → Custom repositories** and add
   `https://github.com/dom42/airbynature` with category **Integration**.
2. Install **AirByNature** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → AirByNature** and
   sign in with your AirByNature app e-mail and password.

## What you get

Each address in your account becomes a device (for example "Gerdavej 14").
Each ventilation unit at that address becomes a device linked to it.

**Address device**

- Sensors: average temperature, mode, current rule, inlets paused until,
  paused until (disabled by default), status
- Binary sensors: rule enabled, drying
- Controls: target temperature (0–40 °C), pause inlets (hours, 0 stops the pause)

**Unit device**

- Sensors: inlet, outlet and outdoor temperature; inlet and outlet humidity;
  CO2 (ppm); TVOC (ppb); inlet and outlet fan (%); fan speeds (rpm)
- Diagnostics: last measurement, Wi-Fi signal, speed factors, measurement
  interval, online, filter, drying heat exchanger
- Control: comfort level (off, very quiet, quiet, normal, high, extra high)

Controls only appear when your account is allowed to use them.

Data is polled every 60 seconds.

## Upgrading from 0.0.1

Remove the old AirByNature integration entry, then add it again. Entity IDs
change in this version.

## Known limitations

- Pause schedules, the schedule and history are not exposed.
- Mode is read-only.
- The Wi-Fi signal is shown as the raw value from the API.
```

- [ ] **Step 4: Full verification**

Run:

```bash
.venv/bin/pytest -v
for f in hacs.json custom_components/airbynature/*.json custom_components/airbynature/translations/*.json; do python3 -m json.tool "$f" > /dev/null || echo "INVALID $f"; done
diff custom_components/airbynature/strings.json custom_components/airbynature/translations/en.json && echo "strings.json == en.json"
git status --short
```

Expected: all tests PASS; no `INVALID` lines; `strings.json == en.json`; `git status` shows only the new/changed files of this task plus the untracked `notes_donot_commit.txt` is **not** listed (ignored) and `no_flo.backup` is **not** listed (ignored).

- [ ] **Step 5: Commit**

```bash
git add hacs.json README.md .github/workflows/hassfest.yml .github/workflows/hacs.yml .github/workflows/tests.yml
git commit -m "Add HACS metadata, CI workflows and README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Hand off manual test to the user**

Tell the user to test on their Home Assistant (this cannot be automated here):

1. Copy `custom_components/airbynature` into their HA `config/custom_components/`, restart.
2. Remove the old AirByNature entry, add the integration again.
3. Check: device "Gerdavej 14" with child "Loftanlæg"; sensor values match the AirByNature app; changing target temperature, comfort level and pause is reflected in the app.
4. Push the branch only after this passes (do not push without the user asking).
