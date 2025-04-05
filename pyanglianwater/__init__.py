"""The core Anglian Water module."""

import calendar
from datetime import date, datetime

from .api import API
from .auth import BaseAuth
from .const import ANGLIAN_WATER_AREAS
from .exceptions import TariffNotAvailableError

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
    current_tariff_rate: float = 0.0
    current_tariff_service: float = None

    def __init__(self, api: API):
        """Init AnglianWater."""
        self.api = api

    def parse_usages(self, _response):
        """Parse given usage details."""
        output = {
            "total": 0.0,
            "cost": 0.0,
            "readings": []
        }
        if "result" in _response:
            _response = _response["result"]["records"]
        previous_read = None
        start_time = None
        end_time = None
        for reading in _response:
            if start_time is None:
                start_time = datetime.fromisoformat(reading["date"])
            end_time = datetime.fromisoformat(reading["date"])
            meter = reading["meters"][0]
            output["total"] += meter["consumption"]
            if previous_read is None:
                previous_read = float(meter["read"])
                continue
            if self.current_tariff_rate is not None:
                read = float(meter["read"])
                output["cost"] += (read - previous_read) * self.current_tariff_rate
                previous_read = read
                continue
                
        output["cost"] += (self.current_tariff_rate / days_in_year(start_time.year)) * days(start_time, end_time)
        output["readings"] = _response
        return output

    async def get_usages(self) -> dict:
        """Calculates the usage using the provided date range."""
        while True:
            _response = await self.api.send_request(
                endpoint="get_usage_details", body=None)
            break

        return self.parse_usages(_response)

    async def update(self):
        """Update cached data."""
        usages = await self.get_usages()
        self.current_usage = usages["total"]
        self.current_readings = usages["readings"]
        self.current_cost = usages["cost"]

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
        await self.update()
        return self
