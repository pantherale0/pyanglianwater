"""Represent a smart water meter."""

from datetime import datetime, timedelta

class SmartMeter:
    """
    A class to represent a smart water meter.
    """

    last_reading: float = 0.0

    def __init__(
            self,
            serial_number,
            tariff_config = None
        ):
        self.serial_number = serial_number
        self.readings = []
        self._tariff_config = tariff_config

    @property
    def tariff_rate(self) -> float:
        """Returns the tariff rate for the smart meter."""
        if self._tariff_config is None:
            return 0.0
        return self._tariff_config(datetime.now()).get("rate", 0.0)

    def update_reading_cache(
            self,
            reads: list
        ):
        """Updates the cache of meter reads for the smart meter."""
        self.readings = []
        for reading in reads:
            for meter in reading["meters"]:
                if meter["meter_serial_number"] == self.serial_number:
                    self.readings.append(meter)
                    self.last_reading = float(meter["read"])

    @property
    def get_yesterday_readings(self) -> list:
        """Returns the the previous days readings for the smart meter."""
        yesterday = datetime.now() - timedelta(days=1)
        output = []
        for reading in self.readings:
            if datetime.fromisoformat(reading["read_at"]).date() == yesterday.date():
                output.append(reading)
        return output

    @property
    def get_yesterday_cost(self) -> float:
        """Returns the cost of the previous days readings for the smart meter."""
        total = 0.0
        previous_read = None
        for reading in self.get_yesterday_readings:
            if previous_read is None:
                previous_read = float(reading["read"])
                continue
            total += (reading["read"] - previous_read) * self._tariff_config(
                datetime.fromisoformat(reading["read_at"])).get("rate", 0.0)
            previous_read = float(reading["read"])
        return total

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

    def to_dict(self) -> dict:
        """Returns the SmartMeter object data as a dictionary."""
        return {
            "serial_number": self.serial_number,
            "last_reading": self.last_reading,
            "readings": self.readings,
            "tariff_rate": self.tariff_rate,
            "consumption": self.latest_consumption,
        }

    def __iter__(self):
        """Allows the object to be converted to a dictionary using dict()."""
        return iter(self.to_dict().items())
