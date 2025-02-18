"""The core Anglian Water module."""

import json

import calendar
from datetime import date, timedelta, datetime

import requests
import fiscalyear

from .api import API
from .const import AW_TARIFF_URL
from .enum import UsagesReadGranularity
from .exceptions import TariffNotAvailableError, ExpiredAccessTokenError

def days_in_year(year):
    """Return number of days in a year."""
    return 365 + calendar.isleap(year)

def days(s: date, e: date):
    """Get number of days between two dates."""
    if isinstance(s, datetime):
        s = s.date()
    if isinstance(e, datetime):
        e = e.date()
    return (e-s).days

ANGLIAN_WATER_AREAS = {}
def load_aw_areas():
    """Helper function to load the AW area cache."""
    global ANGLIAN_WATER_AREAS
    ANGLIAN_WATER_AREAS = json.loads(requests.get(
            url=AW_TARIFF_URL,
            timeout=15).text
    )

class AnglianWater:
    """Anglian Water"""
    api: API = None
    current_usage: float = None
    current_cost: float = None
    current_readings: list = None
    estimated_charge: float = None
    current_balance: float = None
    next_bill_date: date = None
    current_tariff: str = None
    current_tariff_area: str = None
    _custom_rate: float = None
    _custom_service: float = None

    @property
    def current_tariff_rate(self):
        """Get the current tariff rate."""
        if self._custom_rate:
            return self._custom_rate
        return self.get_tariff_config(date.today()).get("rate", 0.0)

    @property
    def current_tariff_service(self):
        """Get the current tariff standing charge."""
        if self._custom_service:
            return self._custom_service
        return self.get_tariff_config(date.today()).get("service", 0.0)

    def get_tariff_config(self, dt: datetime | date) -> dict:
        """Get the tariff rate for a given year."""
        with fiscalyear.fiscal_calendar("same", start_month=4, start_day=1):
            f = fiscalyear.FiscalDate(
                year=dt.year,
                month=dt.month,
                day=dt.day
            )
        charges_year = f"{str(int(f.fiscal_year)-1)}-{str(f.fiscal_year)[2:]}"
        return ANGLIAN_WATER_AREAS.get(
            self.current_tariff_area, {}
        ).get(
            charges_year, {}
        ).get(
            self.current_tariff, {}
        )

    def parse_usages(self, _response, start, end):
        """Parse given usage details."""
        output = {
            "total": 0.0,
            "cost": 0.0,
            "readings": []
        }
        if "Data" in _response:
            _response = _response["Data"][0]
        previous_read = None
        for reading in _response["MyUsageHistoryDetails"]:
            output["total"] += reading["consumption"]
            if previous_read is None:
                previous_read = int(reading["meterReadValue"]) / 1000
                continue
            if self.current_tariff_rate is not None:
                read = int(reading["meterReadValue"]) / 1000
                output["cost"] += (read - previous_read) * self.current_tariff_rate
                previous_read = read
                continue
        output["cost"] += (self.current_tariff_rate / days_in_year(start.year)) * days(start, end)
        output["readings"] = _response["MyUsageHistoryDetails"]
        return output

    async def get_usages(self, start: date, end: date) -> dict:
        """Calculates the usage using the provided date range."""
        retry = False
        while True:
            try:
                _response = await self.api.send_request(
                    endpoint="get_usage_details",
                    body={
                        "ActualAccountNo": self.api.account_number,
                        "EmailAddress": self.api.username,
                        "IsHomeComparision": False,
                        "OccupierCount": 0,
                        "PrimaryBPNumber": self.api.primary_bp_number,
                        "ReadGranularity": str(UsagesReadGranularity.HOURLY),
                        "Selected{}EndDate": end.strftime("%d/%m/%Y"),
                        "SelectedStartDate": start.strftime("%d/%m/%Y")
                    })
                break
            except ExpiredAccessTokenError as exc:
                if not retry:
                    await self.api.refresh_login()
                    retry = True
                else:
                    raise ExpiredAccessTokenError from exc

        return self.parse_usages(_response, start, end)

    async def update(self):
        """Update cached data."""
        # collect tariff information
        if self.current_tariff is None:
            # try and get the tariff information
            bills = await self.api.send_request(
                "get_bills_payments",
                body={
                    "ActualAccountNo": self.api.account_number,
                    "EmailAddress": self.api.username,
                    "PrimaryBPNumber": self.api.primary_bp_number,
                    "SelectedEndDate": date.today().strftime("%d/%m/%Y"),
                    "SelectedStartDate": (
                        datetime.now() - timedelta(days=1825)
                    ).strftime("%d/%m/%Y")
                }
            )
            if "Data" in bills:
                bills = bills["Data"]
            if len(bills) > 0:
                bills = bills[0]
            if bills.get("HasWaterSureTariff", False):
                self.current_tariff = "WaterSure"
            else:
                self.current_tariff = "Standard"
                if self.current_tariff_area is None:
                    self.current_tariff_area = "Anglian"
            if bills["NextBillDate"] is not None:
                self.next_bill_date = bills["NextBillDate"]

        # only historical data is available
        usages = await self.get_usages(date.today()-timedelta(days=1),
                                       date.today()-timedelta(days=1))
        self.current_usage = usages["total"]
        self.current_readings = usages["readings"]
        self.current_cost = usages["cost"]

    @classmethod
    async def create_from_api(
        cls,
        api: API,
        area: str,
        tariff: str = None,
        custom_rate: float = None,
        custom_service: float = None
    ) -> 'AnglianWater':
        """Create a new instance of Anglian Water from the API."""
        self = cls()
        self.api = api
        load_aw_areas()
        if area is not None and area not in ANGLIAN_WATER_AREAS:
            raise TariffNotAvailableError("The provided tariff does not exist.")
        if area is not None:
            self.current_tariff_area = area
        if tariff is not None and area in ANGLIAN_WATER_AREAS:
            if tariff not in ANGLIAN_WATER_AREAS[area]:
                raise TariffNotAvailableError("The provided tariff does not exist.")
            self.current_tariff = tariff
            if self.get_tariff_config(date.today()).get("custom", False):
                self._custom_rate = custom_rate
                self._custom_rate = custom_service
        await self.update()
        return self
