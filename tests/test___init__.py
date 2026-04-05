"""Tests for the AnglianWater module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyanglianwater import (
    AnglianWater,
    API,
    SmartMeter,
)
from pyanglianwater.auth import MSOB2CAuth


@pytest.fixture
def mock_authenticator():  # pylint: disable=redefined-outer-name
    """Fixture for a mocked MSOB2CAuth object."""
    return MagicMock(spec=MSOB2CAuth)


@pytest.fixture
def anglian_water(mock_authenticator):  # pylint: disable=redefined-outer-name
    """Fixture for an AnglianWater instance."""
    return AnglianWater(authenticator=mock_authenticator)


def test_initialization(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that AnglianWater initializes with correct default values."""
    assert anglian_water.meters == {}
    assert anglian_water.account_config == {}
    assert anglian_water.updated_data_callbacks == []
    assert isinstance(anglian_water.api, API)


@pytest.mark.asyncio
async def test_parse_usages(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that parse_usages correctly creates SmartMeter instances."""
    mock_response = [
        {
            "meters": [
                {
                    "meter_serial_number": "12345",
                    "read": 100.0,
                    "consumption": 10.0,
                    "read_at": "2023-10-01T00:00:00Z",
                }
            ]
        }
    ]
    mock_costs = {}
    await anglian_water.parse_usages(mock_response, mock_costs, update_cache=False)
    assert "12345" in anglian_water.meters
    assert isinstance(anglian_water.meters["12345"], SmartMeter)


@pytest.mark.asyncio
async def test_get_usages(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that get_usages fetches and parses usage data correctly."""
    account_number = "12345"
    anglian_water.api.send_request = AsyncMock(
        side_effect=[
            {
                "result": {
                    "records": [
                        {
                            "meters": [
                                {
                                    "meter_serial_number": "12345",
                                    "read": 100.0,
                                    "consumption": 10.0,
                                    "read_at": "2023-10-01T00:00:00Z",
                                }
                            ]
                        }
                    ]
                }
            },
            {},
        ]
    )
    result = await anglian_water.get_usages(account_number=account_number, update_cache=False)
    assert "12345" in anglian_water.meters
    assert isinstance(result, (dict, list))


@pytest.mark.asyncio
async def test_update(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that update validates smart meter and fetches usage data."""
    account_number = "12345"
    anglian_water.api.send_request = AsyncMock(
        side_effect=[
            {"result": {"meter_type": "SmartMeter"}},
            {
                "result": {
                    "records": [
                        {
                            "meters": [
                                {
                                    "meter_serial_number": "12345",
                                    "read": 100.0,
                                    "consumption": 10.0,
                                    "read_at": "2023-10-01T00:00:00Z",
                                }
                            ]
                        }
                    ]
                }
            },
            {},
        ]
    )
    await anglian_water.update(account_number=account_number)


def test_to_dict(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that to_dict returns a dictionary with all AnglianWater data."""
    anglian_water.account_config = {"meter_type": "SmartMeter"}
    anglian_water.meters = {
        "12345": MagicMock(to_dict=MagicMock(return_value={"meter_key": "meter_value"}))
    }
    result = anglian_water.to_dict()
    assert "api" in result
    assert result["meters"]["12345"] == {"meter_key": "meter_value"}
    assert "current_tariff" in result
    assert "account_config" in result


def test_register_callback(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that register_callback adds callbacks and validates they are callable."""
    callback = MagicMock()
    anglian_water.register_callback(callback)
    assert callback in anglian_water.updated_data_callbacks

    with pytest.raises(ValueError):
        anglian_water.register_callback("not_callable")


def test_remove_callback(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that remove_callback removes callbacks from the list."""
    callback = MagicMock()
    anglian_water.register_callback(callback)
    assert callback in anglian_water.updated_data_callbacks
    anglian_water.remove_callback(callback)
    assert callback not in anglian_water.updated_data_callbacks
