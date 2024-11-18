import pyanglianwater
import json
import datetime


import pytest

CONST_START = datetime.date(2024, 11, 9)
CONST_END = datetime.date(2024, 11, 10)

def load_response(method: str) -> dict | list:
    with open(f"tests/{method}.json", "r") as file:
        return json.loads(file.read())

def test_login_parser():
    api = pyanglianwater.API()
    api.parse_login_response(load_response("login"))
    assert api.access_token == "AUTH12345678"
    assert api.account_number == "ACTACCT0987654321"
    assert api.primary_bp_number == "ACCBP1234567890"

def test_usage_parser():
    aw = pyanglianwater.AnglianWater()
    aw.current_tariff_rate = 1.5
    data = aw.parse_usages(load_response("readings"), CONST_START, CONST_END)
    assert aw.current_tariff_rate == 1.5
    assert len(data["readings"])==48
