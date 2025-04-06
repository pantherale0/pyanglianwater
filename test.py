"""Testing."""

import os
import logging
import asyncio

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
                account_id=os.environ.get("AW_ACCOUNT_ID") or input("Account ID: "),
                refresh_token=os.environ.get("AW_REFRESH_TOKEN", None),
            )
            await authenticator.send_login_request()
            _LOGGER.debug("Logged in. Ready..")
            _LOGGER.debug("Refresh token: %s", authenticator.refresh_token)
            login = False
        except Exception as exc:
            _LOGGER.error(exc)

    water = await AnglianWater.create_from_authenticator(authenticator, area="Anglian", tariff="Standard")
    await water.update()
    _LOGGER.debug(">> Got AnglianWater data %s", dict(water))

    while True:
        for m in water.meters.values():
            _LOGGER.debug(">> Meter %s", m.serial_number)
            _LOGGER.debug(">> Last reading %s", m.last_reading)
            _LOGGER.debug(">> Yesterday readings %s", m.get_yesterday_readings)
            _LOGGER.debug(">> Yesterday cost %s", m.get_yesterday_cost)
        await asyncio.sleep(30)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
