"""Unit tests for pyanglianwater.meter module."""

from datetime import datetime, timedelta

import pytest
from pyanglianwater.meter import SmartMeter


@pytest.fixture
def sample_readings():
    """Fixture for sample meter readings data."""
    yesterday = datetime.now() - timedelta(days=1)
    return [
        {
            "meters": [
                {
                    "meter_serial_number": "12345",
                    "read": 100.0,
                    "consumption": 10.0,
                    "read_at": yesterday.isoformat(),
                },
                {
                    "meter_serial_number": "67890",
                    "read": 200.0,
                    "consumption": 20.0,
                    "read_at": yesterday.isoformat(),
                },
            ]
        }
    ]


@pytest.fixture
def smart_meter():
    """Fixture for a SmartMeter instance."""
    return SmartMeter(serial_number="12345")


def test_update_reading_cache(smart_meter, sample_readings):  # pylint: disable=redefined-outer-name
    """Test that update_reading_cache correctly updates the readings cache."""
    smart_meter.update_reading_cache(sample_readings, {})
    assert len(smart_meter.readings) == 1
    assert smart_meter.readings[0]["meter_serial_number"] == "12345"
    assert smart_meter.last_reading == 100.0


def test_get_yesterday_readings(smart_meter, sample_readings):  # pylint: disable=redefined-outer-name
    """Test that get_yesterday_readings returns readings from the previous day."""
    smart_meter.update_reading_cache(sample_readings, {})
    yesterday_readings = smart_meter.get_yesterday_readings
    assert len(yesterday_readings) == 1
    assert yesterday_readings[0]["read"] == 100.0


def test_get_yesterday_cost(smart_meter, sample_readings):  # pylint: disable=redefined-outer-name
    """Test that yesterday cost properties are correctly set from the cache."""
    smart_meter.update_reading_cache(sample_readings, {})
    assert smart_meter.yesterday_water_cost == 0.0
    assert smart_meter.yesterday_sewerage_cost == 0.0


def test_get_yesterday_consumption(smart_meter, sample_readings):  # pylint: disable=redefined-outer-name
    """Test that get_yesterday_consumption returns correct consumption total."""
    smart_meter.update_reading_cache(sample_readings, {})
    consumption = smart_meter.get_yesterday_consumption
    assert consumption == 10.0


def test_latest_consumption(smart_meter, sample_readings):  # pylint: disable=redefined-outer-name
    """Test that latest_consumption returns the most recent consumption value."""
    smart_meter.update_reading_cache(sample_readings, {})
    latest_consumption = smart_meter.latest_consumption
    assert latest_consumption == 10.0


def test_latest_read(smart_meter, sample_readings):  # pylint: disable=redefined-outer-name
    """Test that latest_read returns the most recent meter reading."""
    smart_meter.update_reading_cache(sample_readings, {})
    latest_read = smart_meter.latest_read
    assert latest_read == 100.0


def test_to_dict(smart_meter, sample_readings):  # pylint: disable=redefined-outer-name
    """Test that to_dict returns a dictionary with all meter data."""
    smart_meter.update_reading_cache(sample_readings, {})
    meter_dict = smart_meter.to_dict()
    assert meter_dict["serial_number"] == "12345"
    assert meter_dict["last_reading"] == 100.0
    assert meter_dict["consumption"] == 10.0
    assert len(meter_dict["readings"]) == 1
