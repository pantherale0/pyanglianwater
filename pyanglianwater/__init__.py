"""The core Anglian Water module."""

from typing import Callable
from datetime import datetime as dt

import fiscalyear

from .api import API
from .auth import BaseAuth
from .enum import UsagesReadGranularity
from .exceptions import TariffNotAvailableError, SmartMeterUnavailableError
from .meter import SmartMeter
from .utils import is_awaitable

class AnglianWater:
    """Anglian Water"""

    def __init__(
            self,
            authenticator: BaseAuth,
            area: str | None = None,
            custom_rate: float | None = None,
            custom_service: float | None = None,):
        """Init AnglianWater."""
        self.api = API(authenticator)
        self.meters: dict[str, SmartMeter] = {}
        self.account_config: dict = {}
        self.tariff_config: dict | None = None
        self._custom_rate: float | None = custom_rate
        self._custom_service: float | None = custom_service
        self._area: str | None = area
        self.updated_data_callbacks: list[Callable] = []
        self._first_update = True

    @property
    def current_tariff(self) -> str:
        """Get the current tariff from the account config."""
        tariff: str = self.account_config.get("tariff", "Standard")
        return tariff.replace("tariff", "").strip()

    @property
    def current_tariff_rate(self) -> float:
        """Get the current tariff rate from the tariff config."""
        return self.get_tariff_rate(dt.now())

    @property
    def current_tariff_service(self) -> float:
        """Get the current tariff service from the tariff config."""
        return self.get_tariff_service(dt.now())

    def get_tariff_service(self, date: dt) -> float:
        """Get the tariff service."""
        if self._custom_service is not None:
            return self._custom_service
        return self.get_tariff_config(date).get("service", 0.0)

    def get_tariff_rate(self, date: dt) -> float:
        """Get the tariff rate."""
        if self._custom_rate is not None:
            return self._custom_rate
        return self.get_tariff_config(date).get("rate", 0.0)

    def get_tariff_config(self, date: dt) -> dict:
        """Get the tariff config."""
        return self.tariff_config.get(
            self.get_tariff_year(date), {}
        )

    def get_tariff_year(self, date: dt) -> dict:
        """Get the current tariff year."""
        with fiscalyear.fiscal_calendar("same", start_month=4, start_day=1):
            finyear = fiscalyear.FiscalDate(
                year=date.year,
                month=date.month,
                day=date.day
            )
        return f"{str(int(finyear.fiscal_year))}-{str(finyear.fiscal_year+1)[2:]}"

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
                    tariff_config=self.get_tariff_config
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

    async def validate_smart_meter(self):
        """Validates the account has a smart meter."""
        self.account_config = await self.api.send_request(
                endpoint="get_account",
                body=None
            )
        self.account_config = self.account_config.get("result", {})
        meter_type = self.account_config.get("meter_type", "")
        if meter_type not in {"SmartMeter", "EnhancedSmartMeter"}:
            raise SmartMeterUnavailableError("The account does not have a smart meter.")

    async def load_tariff_data(self):
        """Load tariff data."""
        self.tariff_config = await self.api.load_tariff_data()
        if self._area is not None and self._area not in self.tariff_config:
            raise TariffNotAvailableError("The provided tariff does not exist.")
        if self.current_tariff is not None and self._area in self.tariff_config:
            if self.current_tariff not in self.tariff_config[self._area]:
                raise TariffNotAvailableError("The tariff on the account does not exist.")
            self.tariff_config = self.tariff_config[self._area][self.current_tariff]
            self._custom_rate = self._custom_rate
            self._custom_service = self._custom_service

    async def update(self):
        """Update cached data."""
        if self._first_update:
            await self.validate_smart_meter()
            await self.load_tariff_data()
            self._first_update = False
        await self.get_usages()

    def to_dict(self) -> dict:
        """Returns the AnglianWater object data as a dictionary."""
        return {
            "api": self.api.to_dict(),
            "meters": {
                k: v.to_dict() for k, v in self.meters.items()
            },
            "current_tariff": self.current_tariff,
            "current_tariff_area": self._area,
            "current_tariff_rate": self.current_tariff_rate,
            "current_tariff_service": self.current_tariff_service,
            "custom_rate": self._custom_rate,
            "custom_service": self._custom_service,
            "tariff_config": self.tariff_config,
            "current_tariff_year": self.get_tariff_year(dt.now()),
            "account_config": self.account_config,
        }

    def __iter__(self):
        """Allows the object to be converted to a dictionary using dict()."""
        return iter(self.to_dict().items())

    def register_callback(self, callback):
        """Register a callback to be called when data is updated."""
        if not callable(callback):
            raise ValueError("Callback must be callable")
        self.updated_data_callbacks.append(callback)
