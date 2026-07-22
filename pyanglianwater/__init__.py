"""The core Anglian Water module."""

import logging

from typing import Callable
from datetime import timedelta, datetime as dt

from .api import API
from .auth import MSOB2CAuth
from .const import AW_COST_SUPPORTED_TARIFFS
from .enum import UsagesReadGranularity
from .exceptions import SmartMeterUnavailableError, UnknownEndpointError
from .billing import BillingSummary
from .meter import SmartMeter, UsageComparison
from .utils import is_awaitable, parse_iso_datetime

_LOGGER = logging.getLogger(__name__)


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
        self.comparison: UsageComparison | None = None
        self.billing: BillingSummary | None = None
        self.updated_data_callbacks: list[Callable] = []
        self._data_delay: int = 1  # number of days to 'delay' the data
        self._data_delay_manual: bool = False
        self._first_update = True

    @property
    def data_delay(self) -> int:
        """Number of days to delay data (e.g. for cost window start)."""
        return self._data_delay

    @data_delay.setter
    def data_delay(self, value: int) -> None:
        """Manually set data delay; locks out auto-derivation from usage metadata."""
        self._data_delay = value
        self._data_delay_manual = True

    @property
    def current_tariff(self) -> str:
        """Get the current tariff from the account config."""
        tariff: str = self.account_config.get("tariff", "Standard")
        return tariff.replace("tariff", "").strip()

    async def parse_usages(self, _response, _costs, update_cache: bool = True) -> dict:
        """Parse given usage details."""
        first_meter_read_date = None
        last_meter_read_date = None
        if isinstance(_response, dict):
            result = _response["result"] if "result" in _response else _response
            if isinstance(result, dict):
                first_raw = result.get("first_meter_read_date")
                last_raw = result.get("last_meter_read_date")
                if first_raw:
                    first_meter_read_date = parse_iso_datetime(first_raw)
                if last_raw:
                    last_meter_read_date = parse_iso_datetime(last_raw)
                    if last_meter_read_date is not None and not self._data_delay_manual:
                        lag = (dt.today().date() - last_meter_read_date.date()).days
                        self._data_delay = max(lag, 0)
                _response = result["records"] if "records" in result else result
        if len(_response) == 0:
            return {}
        # Get meter serial numbers from the nested meters dict
        meter_reads = _response[0]["meters"]
        for meter in meter_reads:
            serial_number = meter["meter_serial_number"]
            if serial_number not in self.meters:
                self.meters[serial_number] = SmartMeter(
                    serial_number=serial_number,
                    cost_supported=self.current_tariff in AW_COST_SUPPORTED_TARIFFS
                )
            self.meters[serial_number].first_meter_read_date = first_meter_read_date
            self.meters[serial_number].last_meter_read_date = last_meter_read_date
            if update_cache:
                self.meters[serial_number].update_reading_cache(_response, _costs)
        return _response

    async def get_usages(
        self,
        account_number: str,
        interval: UsagesReadGranularity = UsagesReadGranularity.HOURLY,
        update_cache: bool = True,
    ) -> dict:
        """Calculates the usage using the provided date range."""
        _response = await self.api.send_request(
            endpoint="get_usage_details",
            body=None,
            account_number=account_number,
            GRANULARITY=str(interval),
        )
        # Parse usage first so data_delay can be auto-derived before cost fetch.
        records = await self.parse_usages(_response, {}, update_cache=False)
        start = dt.today().replace(hour=23, minute=0, second=0) - timedelta(
            days=self.data_delay
        )
        _costs = {}
        try:
            if self.current_tariff == "Standard":
                _costs = await self.api.send_request(
                    endpoint="get_usage_costs",
                    body=None,
                    account_number=account_number,
                    GRANULARITY=str(interval),
                    START=start.isoformat(),
                    END=(start + timedelta(days=1)).isoformat(),
                )
            else:
                _LOGGER.info(
                    "Usage costs not available for account %s with tariff %s",
                    account_number,
                    self.current_tariff
                )
        except UnknownEndpointError as exc:
            if exc.status >= 501:
                raise

            _LOGGER.exception(
                "Usage costs not available for account %s (%s) - %s (%s)",
                account_number,
                self.current_tariff,
                start,
                exc.response,
            )
        if update_cache and records:
            for meter_data in records[0]["meters"]:
                serial_number = meter_data["meter_serial_number"]
                self.meters[serial_number].update_reading_cache(records, _costs)
        return records

    async def get_comparison(self, account_number: str) -> UsageComparison:
        """Get usage comparison data."""
        _response = await self.api.send_request(
            endpoint="get_comparison",
            body=None,
            account_number=account_number,
        )
        result = _response.get("result", _response)
        self.comparison = UsageComparison(result)
        return self.comparison

    async def get_billing_summary(self, account_number: str) -> BillingSummary:
        """Get billing summary data."""
        try:
            _response = await self.api.send_request(
                endpoint="get_account_summary",
                body=None,
                account_number=account_number,
                HAS_PAYMENT_ARRANGEMENT=str(
                    self.account_config.get("has_payment_arrangement", False)
                ).lower(),
                HAS_FUTURE_MOVE_IN=str(
                    self.account_config.get("has_future_move_in", False)
                ).lower(),
                HAS_COURT_ACCOUNT=str(
                    self.account_config.get("has_court_account", False)
                ).lower(),
            )
        except UnknownEndpointError as exc:
            if exc.status >= 500:
                raise

            _LOGGER.exception(
                "Billing summary not available for account %s (%s)",
                account_number,
                exc.response,
            )
        else:
            result = (
                _response.get("result", _response) if isinstance(_response, dict) else _response
            )
            self.billing = BillingSummary(result)
            return self.billing

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
        await self.get_comparison(account_number)
        await self.get_usages(account_number)
        await self.get_billing_summary(account_number)
        for callback in self.updated_data_callbacks:
            if is_awaitable(callback):
                await callback()
            else:
                callback()

    def to_dict(self) -> dict:
        """Returns the AnglianWater object data as a dictionary."""
        return {
            "api": self.api.to_dict(),
            "meters": {k: v.to_dict() for k, v in self.meters.items()},
            "current_tariff": self.current_tariff,
            "account_config": self.account_config,
            "comparison": self.comparison.to_dict() if self.comparison else None,
            "billing": self.billing.to_dict() if self.billing else None,
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
