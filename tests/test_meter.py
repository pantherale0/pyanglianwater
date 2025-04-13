import pytest
from datetime import datetime, timedelta
from pyanglianwater.meter import SmartMeter

@pytest.fixture
def sample_readings():
    yesterday = datetime.now() - timedelta(days=1)
    return [
        {
            "meters": [
                {
                    "meter_serial_number": "12345",
                    "read": 100.0,
                    "consumption": 10.0,
                    "read_at": yesterday.isoformat()
                },
                {
                    "meter_serial_number": "67890",
                    "read": 200.0,
                    "consumption": 20.0,
                    "read_at": yesterday.isoformat()
                }
            ]
        }
    ]

@pytest.fixture
def smart_meter():
    return SmartMeter(serial_number="12345", tariff_rate=0.5)

def test_update_reading_cache(smart_meter, sample_readings):
    smart_meter.update_reading_cache(sample_readings)
    assert len(smart_meter.readings) == 1
    assert smart_meter.readings[0]["meter_serial_number"] == "12345"
    assert smart_meter.last_reading == 100.0

def test_get_yesterday_readings(smart_meter, sample_readings):
    smart_meter.update_reading_cache(sample_readings)
    yesterday_readings = smart_meter.get_yesterday_readings
    assert len(yesterday_readings) == 1
    assert yesterday_readings[0]["read"] == 100.0

def test_get_yesterday_cost(smart_meter, sample_readings):
    smart_meter.update_reading_cache(sample_readings)
    cost = smart_meter.get_yesterday_cost
    assert cost == 0.0  # Only one reading, so no cost calculation

def test_get_yesterday_consumption(smart_meter, sample_readings):
    smart_meter.update_reading_cache(sample_readings)
    consumption = smart_meter.get_yesterday_consumption
    assert consumption == 10.0

def test_latest_consumption(smart_meter, sample_readings):
    smart_meter.update_reading_cache(sample_readings)
    latest_consumption = smart_meter.latest_consumption
    assert latest_consumption == 10.0

def test_latest_read(smart_meter, sample_readings):
    smart_meter.update_reading_cache(sample_readings)
    latest_read = smart_meter.latest_read
    assert latest_read == 100.0

def test_to_dict(smart_meter, sample_readings):
    smart_meter.update_reading_cache(sample_readings)
    meter_dict = smart_meter.to_dict()
    assert meter_dict["serial_number"] == "12345"
    assert meter_dict["last_reading"] == 100.0
    assert meter_dict["tariff_rate"] == 0.5
    assert meter_dict["consumption"] == 10.0
    assert len(meter_dict["readings"]) == 1