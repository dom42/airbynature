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
