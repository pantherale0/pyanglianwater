"""The core Anglian Water module."""

from typing import Callable

from .api import API
from .auth import BaseAuth
from .const import ANGLIAN_WATER_AREAS
from .enum import UsagesReadGranularity
from .exceptions import TariffNotAvailableError
from .meter import SmartMeter
from .utils import is_awaitable

class AnglianWater:
    """Anglian Water"""

    api: API = None
    meters: dict[str, SmartMeter] = {}
    current_tariff: str = None
    current_tariff_area: str = None
    current_tariff_rate: float = 0.0
    current_tariff_service: float = None
    updated_data_callbacks: list[Callable] = []

    def __init__(self, api: API):
        """Init AnglianWater."""
        self.api = api

    async def parse_usages(self, _response, update_cache: bool = True) -> dict:
        """Parse given usage details."""
        if "result" in _response:
            _response = _response["result"]
        if "records" in _response:
            _response = _response["records"]
        if len(_response) == 0:
            return {}
        # Get meter serial numbers from the nested meters dict
        meter_reads = _response[0]["meters"]
        for meter in meter_reads:
            serial_number = meter["meter_serial_number"]
            if serial_number not in self.meters:
                self.meters[serial_number] = SmartMeter(
                    serial_number=serial_number,
                    tariff_rate=self.current_tariff_rate
                )
            if update_cache:
                self.meters[serial_number].update_reading_cache(_response)
        for callback in self.updated_data_callbacks:
            if is_awaitable(callback):
                await callback()
            else:
                callback()
        return _response

    async def get_usages(
            self,
            interval: UsagesReadGranularity = UsagesReadGranularity.HOURLY,
            update_cache: bool = True
        ) -> dict:
        """Calculates the usage using the provided date range."""
        while True:
            _response = await self.api.send_request(
                endpoint="get_usage_details", body=None, GRANULARITY=str(interval))
            break
        return await self.parse_usages(_response, update_cache)

    async def update(self):
        """Update cached data."""
        await self.get_usages()

    def to_dict(self) -> dict:
        """Returns the AnglianWater object data as a dictionary."""
        return {
            "api": self.api.to_dict(),
            "meters": {
                k: v.to_dict() for k, v in self.meters.items()
            },
            "current_tariff": self.current_tariff,
            "current_tariff_area": self.current_tariff_area,
            "current_tariff_rate": self.current_tariff_rate,
            "current_tariff_service": self.current_tariff_service
        }

    def __iter__(self):
        """Allows the object to be converted to a dictionary using dict()."""
        return iter(self.to_dict().items())

    def register_callback(self, callback):
        """Register a callback to be called when data is updated."""
        if not callable(callback):
            raise ValueError("Callback must be callable")
        self.updated_data_callbacks.append(callback)

    @classmethod
    async def create_from_authenticator(
        cls,
        authenticator: BaseAuth,
        area: str,
        tariff: str = None,
        custom_rate: float = None,
        custom_service: float = None
    ) -> 'AnglianWater':
        """Create a new instance of Anglian Water from the API."""
        self = cls(API(authenticator))
        if area is not None and area not in ANGLIAN_WATER_AREAS:
            raise TariffNotAvailableError("The provided tariff does not exist.")
        if area is not None:
            self.current_tariff_area = area
        if tariff is not None and area in ANGLIAN_WATER_AREAS:
            if tariff not in ANGLIAN_WATER_AREAS[area]:
                raise TariffNotAvailableError("The provided tariff does not exist.")
            self.current_tariff = tariff
            if ANGLIAN_WATER_AREAS[area][tariff].get("custom", False):
                self.current_tariff_rate = custom_rate
                self.current_tariff_service = custom_service
            else:
                self.current_tariff_rate = ANGLIAN_WATER_AREAS[area][tariff]["rate"]
                self.current_tariff_service = ANGLIAN_WATER_AREAS[area][tariff]["service"]
        return self
