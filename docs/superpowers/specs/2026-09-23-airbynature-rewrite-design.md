# AirByNature integration rewrite — design

Date: 2026-09-23
Branch: `rewrite`

## Goal

Replace the current AirByNature Home Assistant custom integration with a clean
rewrite. Communication with the AirByNature cloud already works; the problem is
that the data exposed in Home Assistant is wrong (sensors matched by entity_id
strings, placeholder device info, only the first group and first unit read,
comfort level sent to every unit).

Success means:

- Each AirByNature device group appears as a Home Assistant device named from the
  group's `address` (e.g. "Gerdavej 14"), and each physical unit in the group
  appears as a child device linked to it via `via_device`.
- All values the API returns are exposed with correct units, device classes and
  entity categories, and each value comes from the right group/unit.
- Target temperature, comfort level and inlet pause can be controlled from Home
  Assistant.
- Accounts with several groups and groups with several units work.
- The integration follows current Home Assistant developer guidelines and passes
  HACS and hassfest validation.

Out of scope: pause schedules (`pause_time`), `schedule`, history endpoints,
changing `mode`, the brand icon submission (a follow-up PR to
`home-assistant/brands`).

## Approach

Async API client on `aiohttp` (Home Assistant's shared client session), typed
dataclass models, one `DataUpdateCoordinator` per config entry, and entities
generated from entity-description tables with a `value_fn` per field.

The old files (`AirByNatureApi.py`, `airbynature.py`, `no_flo.backup`) are
removed on the branch. `main` is untouched until merge.

## File layout

```
custom_components/airbynature/
  __init__.py        async_setup_entry / async_unload_entry, runtime_data, platforms
  api.py             AirByNatureClient (aiohttp) + exceptions; no homeassistant imports
  models.py          DeviceGroup, Unit, Measurements, Permissions dataclasses + parsers
  coordinator.py     AirByNatureCoordinator -> dict[int, DeviceGroup]
  entity.py          AirByNatureGroupEntity, AirByNatureUnitEntity (DeviceInfo, unique_id)
  sensor.py
  binary_sensor.py
  number.py          target temperature, pause inlets
  select.py          comfort level
  config_flow.py     user step + reauth step
  diagnostics.py     redacted config entry + coordinator data
  const.py
  manifest.json
  strings.json
  icons.json
  translations/en.json
  translations/da.json
tests/
  conftest.py
  fixtures/          JSON responses from real captures, secrets removed
  test_api.py
  test_models.py
  test_config_flow.py
  test_init.py
  test_sensor.py
  test_binary_sensor.py
  test_number.py
  test_select.py
  test_diagnostics.py
hacs.json
README.md
.gitignore           includes notes_donot_commit.txt
.github/workflows/   hassfest.yml, hacs.yml, tests.yml
requirements_test.txt
pyproject.toml       pytest configuration
```

## API (from captured traffic)

Base URL `https://admin.airbynature.com`. All JSON calls send
`Authorization: Bearer <token>`.

| Purpose | Request | Notes |
|---|---|---|
| Login | `POST /oauth/token` form: `grant_type=password`, `scope=*`, `username`, `password`, `client_id=1`, `client_secret=angular-app` | Returns `access_token` (1-year expiry) |
| Profile | `GET /api/profile` | `data.id` = user id (config entry unique id) |
| List groups | `GET /api/user-app/devicegroups` | `data[]` of `{id, name}` |
| Group detail | `GET /api/user-app/devicegroups/{gid}` | Full group incl. `devices[]` and `meta.permissions` |
| Set target temperature | `PUT /api/user-app/devicegroups/{gid}` `{"target_temperature": n}` | Returns full group |
| Pause inlets | `PUT /api/user-app/devicegroups/{gid}` `{"pause_inlets_until": "<ISO UTC>" \| null}` | Returns full group |
| Set comfort level | `PATCH /api/user-app/devicegroups/{gid}/devices/{did}` `{"comfort_level": n}` | Returns partial unit |

Server rate limit observed: 240 requests/minute on API routes.

### Client (`api.py`)

`AirByNatureClient(session, username, password)`:

- `async_login()` — obtains and holds the token in memory (never persisted).
- `async_get_user_id() -> int`
- `async_get_groups() -> list[DeviceGroup]` — list, then detail per group.
- `async_set_target_temperature(gid, value) -> DeviceGroup`
- `async_set_pause_inlets(gid, until: datetime | None) -> DeviceGroup`
- `async_set_comfort_level(gid, did, level) -> None`

Every authenticated request retries once after re-login on HTTP 401.
Exceptions: `AirByNatureError` (base), `AuthError` (login rejected or 401 after
retry), `CannotConnect` (timeout / client error), `ApiError` (other non-2xx).
Request timeout 10 s.

## Models (`models.py`)

Frozen dataclasses built by `from_api(dict)` classmethods:

- `Permissions`: `can_change_temperature`, `can_change_mode`,
  `can_change_comfort_level` (`canChangeAirCirculationLevel`), `can_pause_inlets`.
- `Measurements` (from `latest_history`, may be absent → all `None`):
  `inlet_temp`, `inlet_humid`, `inlet_fan`, `inlet_fan1_rpm`, `inlet_fan2_rpm`,
  `outlet_temp`, `outlet_humid`, `outlet_co2`, `outlet_fan`, `outlet_tvoc`,
  `outlet_fan1_rpm`, `outlet_fan2_rpm`, `external_temp`, `measured_at`.
- `Unit`: `id`, `name`, `type`, `comfort_level`, `is_online`, `wifi_signal`,
  `inlet_speed_factor`, `outlet_speed_factor`, `has_filter`,
  `is_drying_heat_exchanger`, `current_interval`, `serial_number`,
  `measurements`.
- `DeviceGroup`: `id`, `name`, `address`, `target_temperature`, `avg_temp`,
  `mode`, `current_running_rule`, `is_rule_enabled`, `is_drying`, `status`,
  `pause_until`, `pause_inlets_until`, `permissions`, `units: dict[int, Unit]`.

Parsing rules: numeric strings (`avg_temp`, speed factors, diagnostic
`wifi_signal`) → `float`; `0/1` flags → `bool`; ISO timestamps → aware
`datetime` (UTC); missing keys or `null` → `None`. Device name falls back to
`name` when `address` is empty.

## Coordinator

`AirByNatureCoordinator(DataUpdateCoordinator[dict[int, DeviceGroup]])`,
update interval 60 s, stored in `entry.runtime_data`.

- `_async_setup`: login.
- `_async_update_data`: `client.async_get_groups()`; `AuthError` →
  `ConfigEntryAuthFailed`; `AirByNatureError` → `UpdateFailed`.
- `async_apply_group(group)`: after a group PUT, replace that group in `data` and
  call `async_set_updated_data` (no extra poll).
- After a comfort-level PATCH, `async_request_refresh()`.

Groups/units added later appear after the entry is reloaded. Entities whose
group/unit is missing from the latest data report unavailable.

## Devices and entities

Base classes in `entity.py` extend `CoordinatorEntity`, set
`_attr_has_entity_name = True`, and use `translation_key` for names.

- Group device: identifiers `{(DOMAIN, f"group_{gid}")}`, name = address,
  manufacturer "AirByNature", model "Device group".
- Unit device: identifiers `{(DOMAIN, f"unit_{did}")}`, name = unit name,
  manufacturer "AirByNature", model = unit `type`, `serial_number` when present,
  `via_device=(DOMAIN, f"group_{gid}")`.
- Unique IDs: `f"{gid}_{key}"` for group entities, `f"{did}_{key}"` for unit
  entities.
- Unit measurement entities are unavailable when `is_online` is false; the
  Online binary sensor stays available.

### Group entities

| key | Platform | Details |
|---|---|---|
| `avg_temperature` | sensor | TEMPERATURE, °C, MEASUREMENT |
| `mode` | sensor | ENUM, raw API value |
| `current_rule` | sensor | text |
| `pause_inlets_until` | sensor | TIMESTAMP |
| `pause_until` | sensor | TIMESTAMP, disabled by default |
| `status` | sensor | DIAGNOSTIC |
| `rule_enabled` | binary_sensor | |
| `drying` | binary_sensor | |
| `target_temperature` | number | TEMPERATURE, °C, 0–40, step 1; created only if `can_change_temperature` |
| `pause_inlets` | number | DURATION, h, 0–24, step 1; created only if `can_pause_inlets` |

`pause_inlets` value = hours remaining until `pause_inlets_until`, rounded up;
0 when not paused or expired. Setting N > 0 sends now + N hours (UTC ISO with
`Z`); setting 0 sends `null`.

### Unit entities

| key | Platform | Details |
|---|---|---|
| `inlet_temperature` | sensor | TEMPERATURE, °C, MEASUREMENT |
| `outlet_temperature` | sensor | TEMPERATURE, °C, MEASUREMENT |
| `external_temperature` | sensor | TEMPERATURE, °C, MEASUREMENT |
| `inlet_humidity` | sensor | HUMIDITY, %, MEASUREMENT |
| `outlet_humidity` | sensor | HUMIDITY, %, MEASUREMENT |
| `co2` | sensor | CO2, ppm, MEASUREMENT |
| `tvoc` | sensor | VOLATILE_ORGANIC_COMPOUNDS_PARTS, ppb, MEASUREMENT |
| `inlet_fan` | sensor | %, MEASUREMENT |
| `outlet_fan` | sensor | %, MEASUREMENT |
| `inlet_fan1_rpm` | sensor | rpm, MEASUREMENT |
| `outlet_fan1_rpm` | sensor | rpm, MEASUREMENT |
| `inlet_fan2_rpm` | sensor | rpm, MEASUREMENT, disabled by default |
| `outlet_fan2_rpm` | sensor | rpm, MEASUREMENT, disabled by default |
| `last_measurement` | sensor | TIMESTAMP, DIAGNOSTIC |
| `wifi_signal` | sensor | DIAGNOSTIC, MEASUREMENT, unitless (raw API value; scale unknown) |
| `inlet_speed_factor` | sensor | %, DIAGNOSTIC |
| `outlet_speed_factor` | sensor | %, DIAGNOSTIC |
| `interval` | sensor | DURATION, s, DIAGNOSTIC |
| `online` | binary_sensor | CONNECTIVITY, DIAGNOSTIC |
| `filter` | binary_sensor | DIAGNOSTIC |
| `drying_heat_exchanger` | binary_sensor | DIAGNOSTIC |
| `comfort_level` | select | options `off`, `very_quiet`, `quiet`, `normal`, `high`, `extra_high` ↔ 1–6; created only if `can_change_comfort_level` |

All names and select options are translated (en, da) via `strings.json` /
`translations/`. Icons via `icons.json`.

## Config flow

- User step: username + password. Login, fetch user id, `async_set_unique_id`
  (user id), abort if already configured. Title = username (e-mail).
  Errors: `invalid_auth`, `cannot_connect`, `unknown`.
- Reauth step: password form for the existing username; must match the same
  user id; updates entry and reloads.

## Error handling

- Polling failures → `UpdateFailed` (entities unavailable, HA retries).
- Auth failures → `ConfigEntryAuthFailed` (reauth flow).
- Setup: first refresh failures raise `ConfigEntryNotReady` via
  `async_config_entry_first_refresh`.
- Commands: `AirByNatureError` → `HomeAssistantError` with a translation key
  (`command_failed`), so the UI shows an error.

## Diagnostics

`async_get_config_entry_diagnostics` returns the entry data and coordinator
data with `username`, `password`, `address`, and user e-mails redacted via
`async_redact_data`.

## Manifest and HACS

`manifest.json`: `domain` `airbynature`, `name` `AirByNature`, `codeowners`
`["@dom42"]`, `config_flow: true`, `documentation` and `issue_tracker` pointing
at the GitHub repo, `integration_type: hub`, `iot_class: cloud_polling`,
`requirements: []`, `version` `0.1.0`.

`hacs.json`: `name`, `render_readme: true`, `homeassistant: "2025.1.0"`
(remove the invalid `iot_class` key).

README: features, installation via HACS custom repository, configuration,
entity list, known limitations.

## Testing

`pytest-homeassistant-custom-component`, `aioresponses` for HTTP.

- `test_api.py`: login success/failure, 401 → re-login → retry, timeout →
  `CannotConnect`, request bodies for each command.
- `test_models.py`: parsing of the captured group fixture, string floats, nulls,
  missing `latest_history`, timestamps.
- `test_config_flow.py`: success, invalid auth, cannot connect, unknown,
  duplicate account abort, reauth success and wrong-account abort.
- `test_init.py`: setup, unload, device tree (unit `via_device` → group),
  `UpdateFailed` and reauth triggering.
- Platform tests: entity states equal fixture values (guards against the
  current wrong-data bug), permission-gated controls absent when not permitted,
  each control sends the correct request, offline unit → measurement sensors
  unavailable.
- `test_diagnostics.py`: redaction.

CI: `hassfest`, `hacs/action` (category integration), and pytest on push/PR.
