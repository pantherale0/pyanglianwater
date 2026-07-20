"""Represent a smart water meter."""

from datetime import datetime, timedelta

from .utils import parse_iso_datetime


class UsageComparison:
    """
    A class to represent a usage comparison result.
    """

    def __init__(self, data: dict):
        """Initialise UsageComparison from a parsed response dict."""
        self.account_number: str | None = str(data["account_number"]) if data.get("account_number") is not None else None
        self.month: str = data.get("month", "")
        self.previous_month: str = data.get("previous_month", "")
        self.average_daily_consumption_change_percentage: int | float = data.get(
            "average_daily_consumption_change_percentage", 0
        )
        self.total_usage: int | float = data.get("total_usage", 0)
        self.average_daily_usage: int | float = data.get("average_daily_usage", 0)
        self.sector_comparison_postcode: str = data.get("sector_comparison", "")
        self.efficient_home_usage: int | float = data.get("efficient_home_usage", 0)
        self.median_usage: int | float = data.get("median_usage", 0)

    def to_dict(self) -> dict:
        """Returns the UsageComparison object data as a dictionary."""
        return {
            "account_number": self.account_number,
            "month": self.month,
            "previous_month": self.previous_month,
            "average_daily_consumption_change_percentage": self.average_daily_consumption_change_percentage,
            "total_usage": self.total_usage,
            "average_daily_usage": self.average_daily_usage,
            "sector_comparison_postcode": self.sector_comparison_postcode,
            "efficient_home_usage": self.efficient_home_usage,
            "median_usage": self.median_usage,
        }

    def __iter__(self):
        """Allows the object to be converted to a dictionary using dict()."""
        return iter(self.to_dict().items())


class SmartMeter:
    """
    A class to represent a smart water meter.
    """

    last_reading: float = 0.0

    def __init__(self, serial_number):
        self.serial_number = serial_number
        self.readings = []
        self.daily_costs: dict[str, dict] = {}

    def update_reading_cache(self, reads: list, costs: dict):
        """Updates the cache of meter reads for the smart meter.

        costs maps ISO dates to {"total_cost", "water_cost", "sewerage_cost"}
        for each day cost data is available.
        """
        self.readings = []
        for reading in reads:
            for meter in reading["meters"]:
                if meter["meter_serial_number"] == self.serial_number:
                    self.readings.append({**meter})
                    self.last_reading = float(meter["read"])
        self.daily_costs = dict(costs)

    @property
    def latest_cost_date(self) -> str | None:
        """Returns the most recent ISO date with cost data available."""
        if not self.daily_costs:
            return None
        return max(self.daily_costs)

    @property
    def yesterday_water_cost(self) -> float:
        """Returns the water cost for the most recent day with cost data.

        Cost data is published a few days behind readings, so this is the
        latest available day rather than the literal calendar yesterday.
        """
        date = self.latest_cost_date
        if date is None:
            return 0.0
        return float(self.daily_costs[date].get("water_cost", 0.0))

    @property
    def yesterday_sewerage_cost(self) -> float:
        """Returns the sewerage cost for the most recent day with cost data."""
        date = self.latest_cost_date
        if date is None:
            return 0.0
        return float(self.daily_costs[date].get("sewerage_cost", 0.0))

    def get_hourly_costs(self) -> list[dict]:
        """Returns per-reading costs, distributing each day's total cost
        across that day's readings in proportion to consumption."""
        by_day: dict[str, list] = {}
        for reading in self.readings:
            read_at = parse_iso_datetime(reading["read_at"])
            if read_at is None:
                continue
            by_day.setdefault(read_at.date().isoformat(), []).append(reading)
        hourly = []
        for day, rows in by_day.items():
            costs = self.daily_costs.get(day)
            if not costs:
                continue
            day_consumption = sum(float(r["consumption"]) for r in rows)
            if day_consumption <= 0:
                continue
            day_total = float(costs.get("total_cost", 0.0))
            for row in rows:
                hourly.append(
                    {
                        "read_at": row["read_at"],
                        "cost": day_total * float(row["consumption"]) / day_consumption,
                    }
                )
        hourly.sort(key=lambda entry: entry["read_at"])
        return hourly

    @property
    def get_yesterday_readings(self) -> list:
        """Returns the the previous days readings for the smart meter."""
        yesterday = datetime.now() - timedelta(days=1)
        output = []
        for reading in self.readings:
            if (
                dt := parse_iso_datetime(reading["read_at"])
            ) and dt.date() == yesterday.date():
                output.append(reading)
        return output

    @property
    def get_yesterday_consumption(self) -> float:
        """Returns the consumption of the previous days readings for the smart meter."""
        total = 0.0
        for reading in self.get_yesterday_readings:
            total += float(reading["consumption"])
        return total

    @property
    def latest_consumption(self) -> float:
        """Returns the latest consumption for the smart meter."""
        if len(self.readings) == 0:
            return 0.0
        return float(self.readings[-1]["consumption"])

    @property
    def latest_read(self) -> float:
        """Returns the latest read for the smart meter."""
        if len(self.readings) == 0:
            return 0.0
        return float(self.readings[-1]["read"])

    @property
    def last_updated(self) -> datetime | None:
        """Returns the last updated time for the smart meter."""
        if len(self.readings) == 0:
            return None
        return parse_iso_datetime(self.readings[-1]["read_at"])

    def to_dict(self) -> dict:
        """Returns the SmartMeter object data as a dictionary."""
        return {
            "serial_number": self.serial_number,
            "last_reading": self.last_reading,
            "readings": self.readings,
            "consumption": self.latest_consumption,
            "daily_costs": self.daily_costs,
        }

    def __iter__(self):
        """Allows the object to be converted to a dictionary using dict()."""
        return iter(self.to_dict().items())
