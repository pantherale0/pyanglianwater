"""The core Anglian Water module."""

import logging

from typing import Callable
from datetime import timedelta, datetime as dt, time as dt_time

from .api import API
from .auth import MSOB2CAuth
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
        self._first_update = True
        self._daily_costs_cache: dict[str, dict] = {}

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
        records = _response
        if isinstance(records, dict) and "result" in records:
            records = records["result"]
        if isinstance(records, dict) and "records" in records:
            records = records["records"]
        days = set()
        for record in records or []:
            for meter in record.get("meters", []):
                read_at = parse_iso_datetime(meter.get("read_at", ""))
                if read_at is not None:
                    days.add(read_at.date())
        _costs = await self._get_daily_costs(account_number, sorted(days), interval)
        return await self.parse_usages(_response, _costs, update_cache)

    async def _get_daily_costs(
        self,
        account_number: str,
        days: list,
        interval: UsagesReadGranularity,
    ) -> dict:
        """Fetch usage costs for each given day, caching across updates.

        Returns a map of ISO date -> {"total_cost", "water_cost",
        "sewerage_cost"}. Days whose cost data is not yet published (the
        endpoint returns a 500 with an empty errors array for those) are
        skipped rather than treated as fatal.
        """
        costs: dict[str, dict] = {}
        for day in days:
            key = day.isoformat()
            if key in self._daily_costs_cache:
                costs[key] = self._daily_costs_cache[key]
                continue
            # The API groups a day's usage into the 23:00-to-23:00 window
            # ending on that day.
            start = dt.combine(day - timedelta(days=1), dt_time(23, 0))
            try:
                response = await self.api.send_request(
                    endpoint="get_usage_costs",
                    body=None,
                    account_number=account_number,
                    GRANULARITY=str(interval),
                    START=start.isoformat(),
                    END=(start + timedelta(days=1)).isoformat(),
                )
            except UnknownEndpointError as exc:
                _LOGGER.debug(
                    "Usage costs not available for account %s - %s (%s)",
                    account_number,
                    key,
                    exc.response,
                )
                continue
            result = response.get("result") if isinstance(response, dict) else None
            if not isinstance(result, dict):
                continue
            entry = {
                "total_cost": float(result.get("total_cost") or 0.0),
                "water_cost": float(result.get("water_cost") or 0.0),
                "sewerage_cost": float(result.get("sewerage_cost") or 0.0),
            }
            costs[key] = entry
            self._daily_costs_cache[key] = entry
        # Drop cached days that have fallen out of the readings window.
        keep = {day.isoformat() for day in days}
        self._daily_costs_cache = {
            k: v for k, v in self._daily_costs_cache.items() if k in keep
        }
        return costs

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
                HAS_PAYMENT_ARRANGEMENT=str(self.account_config.get("has_payment_arrangement", False)).lower(),
                HAS_FUTURE_MOVE_IN=str(self.account_config.get("has_future_move_in", False)).lower(),
                HAS_COURT_ACCOUNT=str(self.account_config.get("has_court_account", False)).lower(),
            )
        except UnknownEndpointError as exc:
            # Treat server errors the same as client errors here: the backend
            # can 500 when summary data is unavailable, and billing must not
            # fail the wider update cycle.
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
