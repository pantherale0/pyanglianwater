"""Hourly usage failures retain diagnostics without masking other API errors."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from pyanglianwater import AnglianWater
from pyanglianwater.auth import MSOB2CAuth
from pyanglianwater.enum import UsagesReadGranularity
from pyanglianwater.exceptions import UnknownEndpointError

OBSERVED_RESPONSE = '{"result":{"errors":[{"code":"1","description":"Failed to retrieve usage data"}]}}'


@pytest.fixture
async def client():
    """Use real API and authentication handlers with a mocked HTTP response."""
    async with aiohttp.ClientSession() as session:
        auth = MSOB2CAuth("testuser", "testpassword", session)
        auth.auth_data = {"access_token": "test_token"}
        auth.next_refresh = datetime.now(UTC) + timedelta(hours=1)
        yield AnglianWater(auth), session


@pytest.mark.asyncio
async def test_hourly_readings_unavailable(client):
    """The reported failure reaches callers with its original HTTP diagnostics."""
    from pyanglianwater.exceptions import HourlyReadingsUnavailableError

    water, session = client
    response = AsyncMock(ok=False, status=500)
    response.text.return_value = OBSERVED_RESPONSE
    with patch.object(session, "request") as request:
        request.return_value.__aenter__.return_value = response
        with pytest.raises(HourlyReadingsUnavailableError) as caught:
            await water.get_usages("12345")
    assert caught.value.status == 500
    assert caught.value.response == OBSERVED_RESPONSE
    assert isinstance(caught.value.__cause__, UnknownEndpointError)
    assert caught.value.__cause__.response == OBSERVED_RESPONSE
    assert OBSERVED_RESPONSE in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint,granularity,status,body",
    [
        ("get_usage_details", "10", 500, "Internal Server Error"),
        (
            "get_usage_details",
            "10",
            500,
            '{"result":{"errors":[{"code":"2","description":"Failed to retrieve usage data"}]}}',
        ),
        ("get_usage_details", "10", 500, '{"result":{"errors":[{"code":"1","description":"Other failure"}]}}'),
        ("get_usage_details", "10", 500, '{"result":null}'),
        ("get_usage_details", "10", 500, '[]'),
        (
            "get_usage_details",
            "10",
            500,
            '{"result":{"errors":[{"code":"1","description":"Failed to retrieve usage data"},{"code":"2"}]}}',
        ),
        ("get_usage_details", "10", 503, OBSERVED_RESPONSE),
        ("get_usage_details", "20", 500, OBSERVED_RESPONSE),
        ("get_comparison", "10", 500, OBSERVED_RESPONSE),
        ("get_usage_costs", "10", 500, OBSERVED_RESPONSE),
    ],
)
async def test_other_failures_unchanged(client, endpoint, granularity, status, body):
    """Only the identified hourly failure gets a dedicated exception."""
    water, session = client
    response = AsyncMock(ok=False, status=status)
    response.text.return_value = body
    with patch.object(session, "request") as request:
        request.return_value.__aenter__.return_value = response
        with pytest.raises(UnknownEndpointError) as caught:
            if endpoint == "get_usage_details":
                await water.get_usages("12345", interval=UsagesReadGranularity(granularity))
            else:
                await water.api.send_request(endpoint, None, "12345", GRANULARITY=granularity, START="start", END="end")
    assert type(caught.value) is UnknownEndpointError
    assert caught.value.status == status
    assert caught.value.response == body


@pytest.mark.asyncio
async def test_successful_hourly_request(client):
    """Successful usage data passes through unchanged."""
    water, session = client
    payload = {"result": {"records": []}}
    response = AsyncMock(ok=True, status=200, content_type="application/json")
    response.json.return_value = payload
    with patch.object(session, "request") as request:
        request.return_value.__aenter__.return_value = response
        result = await water.api.send_request("get_usage_details", None, "12345", GRANULARITY="10")
    assert result == {"result": {"records": []}}
    assert request.call_args.kwargs["url"].endswith("/usage/smartmeter/frequency/10")


@pytest.mark.asyncio
async def test_api_keeps_hourly_failure_generic(client):
    """The API transport leaves usage interpretation to its caller."""
    water, session = client
    response = AsyncMock(ok=False, status=500)
    response.text.return_value = OBSERVED_RESPONSE
    with patch.object(session, "request") as request:
        request.return_value.__aenter__.return_value = response
        with pytest.raises(UnknownEndpointError) as caught:
            await water.api.send_request("get_usage_details", None, "12345", GRANULARITY="10")
    assert type(caught.value) is UnknownEndpointError
    assert caught.value.response == OBSERVED_RESPONSE


@pytest.mark.asyncio
async def test_usage_costs_500_still_ignored(client):
    """A cost failure does not become an hourly readings failure."""
    water, session = client
    usage_response = AsyncMock(ok=True, status=200, content_type="application/json")
    usage_response.json.return_value = {"result": {"records": []}}
    cost_response = AsyncMock(ok=False, status=500)
    cost_response.text.return_value = OBSERVED_RESPONSE
    with patch.object(session, "request") as request:
        request.return_value.__aenter__.side_effect = [usage_response, cost_response]
        assert await water.get_usages("12345") == {}
    assert request.call_count == 2
