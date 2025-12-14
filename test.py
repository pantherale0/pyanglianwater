"""Testing."""

import os
import logging
import asyncio

import aiohttp

from dotenv import load_dotenv
from pyanglianwater import AnglianWater
from pyanglianwater.auth import MSOB2CAuth

_LOGGER = logging.getLogger(__name__)
load_dotenv()


async def main():
    """Main test module."""
    login = True
    while login:
        try:
            authenticator = MSOB2CAuth(
                username=os.environ.get("AW_USERNAME") or input("Email: "),
                password=os.environ.get("AW_PASSWORD") or input("Password: "),
                refresh_token=os.environ.get("AW_REFRESH_TOKEN", None),
                session=aiohttp.ClientSession(
                    cookie_jar=aiohttp.CookieJar(quote_cookie=False)
                )
            )
            await authenticator.send_login_request()
            _LOGGER.debug("Logged in. Ready..")
            _LOGGER.debug("Refresh token: %s", authenticator.refresh_token)
            _LOGGER.debug("Access token: %s", authenticator.access_token)
            login = False
        except Exception as exc:
            _LOGGER.error(exc)

    water = AnglianWater(authenticator)
    accounts = await water.api.get_associated_accounts()
    _LOGGER.debug(accounts)
    for acct in accounts["result"]["active"]:
        await water.update(str(acct["account_number"]))

    while True:
        for m in water.meters.values():
            _LOGGER.debug(">> Meter %s", m.serial_number)
            _LOGGER.debug(">> Last reading %s", m.last_reading)
            _LOGGER.debug(">> Yesterday cost %s", m.yesterday_water_cost)
            _LOGGER.debug(">> Latest consumption %s", m.latest_consumption)
        await asyncio.sleep(30)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
