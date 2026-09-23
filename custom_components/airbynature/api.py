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
