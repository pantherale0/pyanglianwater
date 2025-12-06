"""The core Anglian Water module."""

from typing import Callable
from datetime import timedelta, datetime as dt

from .api import API
from .auth import MSOB2CAuth
from .enum import UsagesReadGranularity
from .exceptions import SmartMeterUnavailableError
from .meter import SmartMeter
from .utils import is_awaitable


class AnglianWater:
    """Anglian Water"""

    def __init__(
        self,
        authenticator: MSOB2CAuth,
    ):
        """Init AnglianWater."""
        self.api = API(authenticator)
        self.meters: dict[str, SmartMeter] = {}
        self.account_config: dict = {}
        self.updated_data_callbacks: list[Callable] = []
        self._first_update = True

    @property
    def current_tariff(self) -> str:
        """Get the current tariff from the account config."""
        tariff: str = self.account_config.get("tariff", "Standard")
        return tariff.replace("tariff", "").strip()

    async def parse_usages(self, _response, _costs, update_cache: bool = True) -> dict:
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
                self.meters[serial_number] = SmartMeter(serial_number=serial_number)
            if update_cache:
                self.meters[serial_number].update_reading_cache(_response, _costs)
        for callback in self.updated_data_callbacks:
            if is_awaitable(callback):
                await callback()
            else:
                callback()
        return _response

    async def get_usages(
        self,
        account_number: str,
        interval: UsagesReadGranularity = UsagesReadGranularity.HOURLY,
        update_cache: bool = True,
    ) -> dict:
        """Calculates the usage using the provided date range."""
        start = dt.today().replace(hour=23, minute=0, second=0) - timedelta(days=1)
        _response = await self.api.send_request(
            endpoint="get_usage_details",
            body=None,
            account_number=account_number,
            GRANULARITY=str(interval),
        )
        _costs = await self.api.send_request(
            endpoint="get_usage_costs",
            body=None,
            account_number=account_number,
            GRANULARITY=str(interval),
            START=start.isoformat(),
            END=(start + timedelta(days=1)).isoformat(),
        )
        return await self.parse_usages(_response, _costs, update_cache)

    async def validate_smart_meter(self, account_number: str):
        """Validates the account has a smart meter."""
        self.account_config = await self.api.send_request(
            endpoint="get_account", body=None, account_number=account_number
        )
        self.account_config = self.account_config.get("result", {})
        meter_type = self.account_config.get("meter_type", "")
        if meter_type not in {"SmartMeter", "EnhancedSmartMeter"}:
            raise SmartMeterUnavailableError("The account does not have a smart meter.")

    async def update(self, account_number: str):
        """Update cached data."""
        if self._first_update:
            await self.validate_smart_meter(account_number)
            self._first_update = False
        await self.get_usages(account_number)

    def to_dict(self) -> dict:
        """Returns the AnglianWater object data as a dictionary."""
        return {
            "api": self.api.to_dict(),
            "meters": {k: v.to_dict() for k, v in self.meters.items()},
            "current_tariff": self.current_tariff,
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

    def remove_callback(self, callback):
        """Remove a registered callback."""
        if callback in self.updated_data_callbacks:
            self.updated_data_callbacks.remove(callback)
