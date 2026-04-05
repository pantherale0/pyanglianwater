"""Tests for the AnglianWater module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyanglianwater import (
    AnglianWater,
    API,
    SmartMeter,
    UsageComparison,
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


@pytest.mark.asyncio
async def test_get_comparison(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that get_comparison parses the API response into a UsageComparison."""
    sample_response = {
        "result": {
            "account_number": 171260490,
            "month": "March",
            "previous_month": "February",
            "average_daily_consumption_change_percentage": 2,
            "total_usage": 5206,
            "average_daily_usage": 168,
            "sector_comparison": "NR17",
            "efficient_home_usage": 4198,
            "median_usage": 6652,
        }
    }
    anglian_water.api.send_request = AsyncMock(return_value=sample_response)
    result = await anglian_water.get_comparison(account_number="12345")

    assert isinstance(result, UsageComparison)
    assert anglian_water.comparison is result
    assert result.account_number == "171260490"
    assert result.month == "March"
    assert result.previous_month == "February"
    assert result.average_daily_consumption_change_percentage == 2
    assert result.total_usage == 5206
    assert result.average_daily_usage == 168
    assert result.sector_comparison_postcode == "NR17"
    assert result.efficient_home_usage == 4198
    assert result.median_usage == 6652


def test_to_dict_includes_comparison(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that to_dict includes comparison data when available."""
    result = anglian_water.to_dict()
    assert "comparison" in result
    assert result["comparison"] is None

    anglian_water.comparison = UsageComparison(
        {
            "account_number": 171260490,
            "month": "March",
            "previous_month": "February",
            "average_daily_consumption_change_percentage": 2,
            "total_usage": 5206,
            "average_daily_usage": 168,
            "sector_comparison": "NR17",
            "efficient_home_usage": 4198,
            "median_usage": 6652,
        }
    )
    result = anglian_water.to_dict()
    assert result["comparison"]["month"] == "March"
    assert result["comparison"]["sector_comparison_postcode"] == "NR17"
