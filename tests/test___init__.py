import pytest
from unittest.mock import AsyncMock, MagicMock
from pyanglianwater import AnglianWater, API, BaseAuth, SmartMeter, TariffNotAvailableError
from pyanglianwater.enum import UsagesReadGranularity

@pytest.fixture
def mock_api():
    return AsyncMock(spec=API)

@pytest.fixture
def anglian_water(mock_api):
    return AnglianWater(api=mock_api)

def test_initialization(anglian_water, mock_api):
    assert anglian_water.api == mock_api
    assert anglian_water.meters == {}
    assert anglian_water.current_tariff is None
    assert anglian_water.current_tariff_area is None
    assert anglian_water.current_tariff_rate == 0.0
    assert anglian_water.current_tariff_service is None
    assert anglian_water.updated_data_callbacks == []

@pytest.mark.asyncio
async def test_parse_usages(anglian_water):
    mock_response = {
        "result": {
            "records": [
                {
                    "meters": [
                        {"meter_serial_number": "12345",
                         "read": 100.0,
                         "consumption": 10.0,
                         "read_at": "2023-10-01T00:00:00Z",}
                    ]
                }
            ]
        }
    }
    anglian_water.current_tariff_rate = 1.5
    await anglian_water.parse_usages(mock_response)
    assert "12345" in anglian_water.meters
    assert isinstance(anglian_water.meters["12345"], SmartMeter)

@pytest.mark.asyncio
async def test_get_usages(anglian_water):
    anglian_water.api.send_request.return_value = {
        "result": {
            "records": [
                {
                    "meters": [
                        {"meter_serial_number": "12345",
                         "read": 100.0,
                         "consumption": 10.0,
                         "read_at": "2023-10-01T00:00:00Z",}
                    ]
                }
            ]
        }
    }
    result = await anglian_water.get_usages()
    assert "12345" in anglian_water.meters
    assert isinstance(result, dict)

@pytest.mark.asyncio
async def test_update(anglian_water):
    anglian_water.get_usages = AsyncMock()
    await anglian_water.update()
    anglian_water.get_usages.assert_called_once()

def test_to_dict(anglian_water):
    anglian_water.api.to_dict = MagicMock(return_value={"key": "value"})
    anglian_water.meters = {"12345": MagicMock(to_dict=MagicMock(return_value={"meter_key": "meter_value"}))}
    result = anglian_water.to_dict()
    assert result["api"] == {"key": "value"}
    assert result["meters"]["12345"] == {"meter_key": "meter_value"}

def test_register_callback(anglian_water):
    callback = MagicMock()
    anglian_water.register_callback(callback)
    assert callback in anglian_water.updated_data_callbacks

    with pytest.raises(ValueError):
        anglian_water.register_callback("not_callable")

@pytest.mark.asyncio
async def test_create_from_authenticator():
    mock_authenticator = MagicMock(spec=BaseAuth)
    mock_api = MagicMock(spec=API)
    mock_api.send_request = AsyncMock()
    AnglianWater.API = MagicMock(return_value=mock_api)

    anglian_water = await AnglianWater.create_from_authenticator(
        authenticator=mock_authenticator,
        area="Anglian",
        tariff="Standard",
        custom_rate=1.5,
        custom_service=2.0
    )
    assert anglian_water.current_tariff_area == "Anglian"
    assert anglian_water.current_tariff == "Standard"
    assert anglian_water.current_tariff_rate == 2.0954
    assert anglian_water.current_tariff_service == 37.0

    with pytest.raises(TariffNotAvailableError):
        await AnglianWater.create_from_authenticator(
            authenticator=mock_authenticator,
            area="invalid_area"
        )