"""Tests for the AnglianWater module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyanglianwater import (
    AnglianWater,
    API,
    BillingSummary,
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
            {
                "result": {
                    "account_number": 12345,
                    "month": "March",
                    "previous_month": "February",
                    "average_daily_consumption_change_percentage": 2,
                    "total_usage": 5206,
                    "average_daily_usage": 168,
                    "sector_comparison": "NR17",
                    "efficient_home_usage": 4198,
                    "median_usage": 6652,
                }
            },
            {
                "result": {
                    "account_balance": -50.00,
                    "balance_due_date": "2026-03-01T00:00:00Z",
                    "next_payment_amount": 20.00,
                    "next_payment_date": "2026-04-15T00:00:00Z",
                    "next_bill_date": "2026-05-01T02:00:00Z",
                    "balance_type": "Credit",
                    "last_payment_date": "2026-03-15T00:00:00Z",
                    "last_payment_amount": -20.00,
                    "is_behind_with_payment": False,
                    "is_direct_debit_claim_in_progress": False,
                    "payment_arrangement": None,
                    "overdue_amount": 0.00,
                    "has_quotation_payment_scheme": False,
                    "refund_amount": 0.00,
                    "move_out_refund_threshold_amount": -299.0,
                    "second_payment_amount": 0.00,
                    "has_court_balance": False,
                }
            },
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


_MOCK_BILLING_RESPONSE = {
    "result": {
        "account_balance": -50.00,
        "balance_due_date": "2026-03-01T00:00:00Z",
        "next_payment_amount": 20.00,
        "next_payment_date": "2026-04-15T00:00:00Z",
        "next_bill_date": "2026-05-01T02:00:00Z",
        "balance_type": "Credit",
        "last_payment_date": "2026-03-15T00:00:00Z",
        "last_payment_amount": -20.00,
        "is_behind_with_payment": False,
        "is_direct_debit_claim_in_progress": False,
        "payment_arrangement": {
            "payment_type": "DirectDebit",
            "end_term_balance": 100.00,
            "payment_frequency": "Monthly",
            "payment_day": 15,
            "payment_amount": 20.00,
            "are_request_lines_open": True,
            "payment_reminder": False,
            "bill_period_end_date": "2026-05-01T00:00:00Z",
            "regular_payment_amount": 20.00,
            "regular_payment_date": "2026-05-15T00:00:00Z",
            "has_rejected_direct_debit": False,
            "payment_scheme_type": "Measured",
            "has_retained_payment": False,
            "retainment_date": "2026-04-15T00:00:00Z",
            "retainment_amount": 0.00,
            "number_of_retained_payments": 0,
            "has_pending_payment_plan_change": False,
            "retained_payment_frequency": "Monthly",
        },
        "overdue_amount": 0.00,
        "has_quotation_payment_scheme": False,
        "refund_amount": 0.00,
        "move_out_refund_threshold_amount": -299.0,
        "second_payment_amount": 0.00,
        "has_court_balance": False,
    }
}


@pytest.mark.asyncio
async def test_get_billing_summary(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that get_billing_summary parses the API response into a BillingSummary."""
    anglian_water.api.send_request = AsyncMock(return_value=_MOCK_BILLING_RESPONSE)
    result = await anglian_water.get_billing_summary(account_number="12345")

    assert isinstance(result, BillingSummary)
    assert anglian_water.billing is result
    assert result.account_balance == -50.00
    assert result.balance_type == "Credit"
    assert result.next_payment_amount == 20.00
    assert result.is_behind_with_payment is False
    assert result.is_direct_debit_claim_in_progress is False
    assert result.overdue_amount == 0.00
    assert result.has_court_balance is False
    assert result.payment_arrangement is not None
    assert result.payment_arrangement.payment_type == "DirectDebit"
    assert result.payment_arrangement.payment_frequency == "Monthly"
    assert result.payment_arrangement.payment_day == 15
    assert result.payment_arrangement.payment_amount == 20.00
    assert result.payment_arrangement.payment_scheme_type == "Measured"
    assert result.payment_arrangement.number_of_retained_payments == 0


@pytest.mark.asyncio
async def test_get_billing_summary_no_arrangement(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that get_billing_summary handles a missing payment_arrangement."""
    response = {
        "result": {
            "account_balance": 0.00,
            "balance_type": "Neutral",
            "is_behind_with_payment": False,
            "is_direct_debit_claim_in_progress": False,
            "payment_arrangement": None,
            "overdue_amount": 0.00,
            "has_quotation_payment_scheme": False,
            "refund_amount": 0.00,
            "move_out_refund_threshold_amount": 0.00,
            "second_payment_amount": 0.00,
            "has_court_balance": False,
        }
    }
    anglian_water.api.send_request = AsyncMock(return_value=response)
    result = await anglian_water.get_billing_summary(account_number="12345")

    assert isinstance(result, BillingSummary)
    assert result.payment_arrangement is None
    assert result.account_balance == 0.00


def test_to_dict_includes_billing(anglian_water):  # pylint: disable=redefined-outer-name
    """Test that to_dict includes billing data when available."""
    result = anglian_water.to_dict()
    assert "billing" in result
    assert result["billing"] is None

    from pyanglianwater.billing import BillingSummary as _BS

    anglian_water.billing = _BS(_MOCK_BILLING_RESPONSE["result"])
    result = anglian_water.to_dict()
    assert result["billing"]["account_balance"] == -50.00
    assert result["billing"]["balance_type"] == "Credit"
    assert result["billing"]["payment_arrangement"]["payment_type"] == "DirectDebit"
