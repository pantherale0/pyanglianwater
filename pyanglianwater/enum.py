"""Anglian Water enums."""

from enum import StrEnum

class UsagesReadGranularity(StrEnum):
    """Usages Read Granularity."""
    MONTHLY = "30"
    DAILY = "20"
    HOURLY = "10"
