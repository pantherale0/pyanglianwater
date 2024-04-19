"""The core Anglian Water module."""

from datetime import date, timedelta, datetime

from .api import API
from .const import ANGLIAN_WATER_TARIFFS
from .enum import UsagesReadGranularity
from .exceptions import TariffNotAvailableError

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
    current_tariff_rate: float = None

    async def get_usages(self, start: date, end: date) -> dict:
        """Calculates the usage using the provided date range."""
        output = {
            "total": 0.0,
            "cost": 0.0,
            "readings": []
        }
        _response = await self.api.send_request(
            endpoint="get_usage_details",
            body={
                "ActualAccountNo": self.api.account_number,
                "EmailAddress": self.api.username,
                "IsHomeComparision": False,
                "OccupierCount": 0,
                "PrimaryBPNumber": self.api.primary_bp_number,
                "ReadGranularity": str(UsagesReadGranularity.HOURLY),
                "SelectedEndDate": end.strftime("%d/%m/%Y"),
                "SelectedStartDate": start.strftime("%d/%m/%Y")
            })
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

        output["readings"] = _response["MyUsageHistoryDetails"]
        return output

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
                self.current_tariff = "standard"
                self.current_tariff_rate = ANGLIAN_WATER_TARIFFS["standard"]["rate"]
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
        tariff: str = None,
        custom_rate: float = None
    ) -> 'AnglianWater':
        """Create a new instance of Anglian Water from the API."""
        self = cls()
        self.api = api
        if tariff is not None and tariff not in ANGLIAN_WATER_TARIFFS:
            raise TariffNotAvailableError("The provided tariff does not exist.")
        if tariff is not None and tariff in ANGLIAN_WATER_TARIFFS:
            self.current_tariff = tariff
            if ANGLIAN_WATER_TARIFFS[tariff].get("custom", False):
                self.current_tariff_rate = custom_rate
            else:
                self.current_tariff_rate = ANGLIAN_WATER_TARIFFS[tariff]["rate"]
        await self.update()
        return self
