"""Testing."""

import os
import logging
import asyncio

from dotenv import load_dotenv
from pyanglianwater import AnglianWater, API

_LOGGER = logging.getLogger(__name__)
load_dotenv()


async def main():
    """Main test module."""
    login = True
    while login:
        try:
            dev_id = os.environ.get("AW_DEVID") or input("Enter Device ID: ")
            if dev_id != "":
                auth = await API.create_via_login_existing_device(
                    email=os.environ.get("AW_USERNAME") or input("Email: "),
                    password=os.environ.get("AW_PASSWORD") or input("Password: "),
                    dev_id=dev_id
                )
            else:
                auth = await API.create_via_login(
                    email=os.environ.get("AW_USERNAME") or input("Email: "),
                    password=os.environ.get("AW_PASSWORD") or input("Password: "),
                )
            _LOGGER.debug("Logged in. Ready..")
            login = False
        except Exception as exc:
            _LOGGER.error(exc)

    water = await AnglianWater.create_from_api(auth, area="Anglian")
    _LOGGER.debug(">> Got AnglianWater data %s", water.__dict__)

    while True:
        await asyncio.sleep(30)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
