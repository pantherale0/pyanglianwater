"""The core Anglian Water module."""

from datetime import date, timedelta

from .api import API
from .enum import UsagesReadGranularity

class AnglianWater:
    """Anglian Water"""

    api: API = None
    current_usage: float = None
    current_readings: list = None
    estimated_charge: float = None
    current_balance: float = None
    next_bill_date: date = None

    async def get_usages(self, start: date, end: date) -> dict:
        """Calculates the usage using the provided date range."""
        output = {
            "total": 0.0,
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
        for reading in _response["MyUsageHistoryDetails"]:
            output["total"] += reading["consumption"]
        output["readings"] = _response["MyUsageHistoryDetails"]
        return output

    async def update(self):
        """Update cached data."""
        # only historical data is available
        usages = await self.get_usages(date.today()-timedelta(days=1),
                                       date.today()-timedelta(days=1))
        self.current_usage = usages["total"]
        self.current_readings = usages["readings"]

    @classmethod
    async def create_from_api(cls, api: API) -> 'AnglianWater':
        """Create a new instance of Anglian Water from the API."""
        self = cls()
        self.api = api
        await self.update()
        return self
