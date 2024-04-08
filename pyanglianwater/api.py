"""Authentication and API handling for Anglian Water."""

import logging
import secrets
from datetime import datetime, timedelta

import aiohttp

from .const import API_BASEURL, API_ENDPOINTS, API_APP_KEY, API_PARTNER_KEY
from .exceptions import (
    API_RESPONSE_STATUS_CODE_MAPPING,
    ExpiredAccessTokenError,
    UnknownEndpointError
)

_LOGGER = logging.getLogger(__name__)

class API:
    """API Handler for Anglian Water."""

    access_token = None
    username = None
    _password = None
    device_id = None
    ts = None
    account_number = None
    primary_bp_number = None
    next_refresh = None

    def generate_partner_key(self):
        """Generate a partner key for authentication."""
        if self.access_token is None:
            return API_PARTNER_KEY.format(
                EMAIL="undefined",
                TS="undefined",
                DEV_ID=self.device_id,
                APP_KEY=API_APP_KEY
            )
        return API_PARTNER_KEY.format(
                EMAIL=self.username,
                TS=self.ts,
                DEV_ID=self.device_id,
                APP_KEY=API_APP_KEY
            )

    @classmethod
    async def create_via_login(cls, email: str, password: str) -> 'API':
        """Login via username and password."""
        # Generate a device ID.
        self = cls()
        self.username = email
        self._password = password
        self.device_id = secrets.token_hex(8)
        _LOGGER.debug(
            ">> Generated device ID %s. Keep this safe to login to this session in the future.",
            self.device_id)
        await self.refresh_login()
        _LOGGER.debug(
            ">> Some initial queries need to be sent as this is a new device ID.")
        await self.send_request(
            endpoint="register_device",
            body={
                "DeviceId": self.device_id,
                "DeviceOs": "Android",
                "EmailId": self.username,
                "EnableNotif": True,
                "LanguageSetup": "en",
                "Partner": self.primary_bp_number,
                "PartternSetup": False,
                "PreviousEmailId": "",
                "Regikey": "",
                "Vkont": str(self.ts)
            }
        )
        await self.send_request(
            endpoint="register_device",
            body={
                "DeviceId": self.device_id,
                "DeviceOs": "Android",
                "EmailId": self.username,
                "EnableNotif": True,
                "LanguageSetup": "en",
                "Partner": self.primary_bp_number,
                "PartternSetup": True,
                "PreviousEmailId": "",
                "Regikey": "",
                "Vkont": str(self.ts)
            }
        )
        await self.send_request(
            endpoint="get_dashboard_details",
            body={
                "ActualAccountNumber": self.account_number,
                "EmailAddress": self.username,
                "LanguageId": 1
            }
        )
        await self.send_request(
            endpoint="get_bills_payments",
            body={
                "ActualAccountNo": self.account_number,
                "EmailAddress": self.username,
                "PrimaryBPNumber": self.primary_bp_number,
                "SelectedEndDate": datetime.now().strftime("%d/%m/%Y"),
                "SelectedStartDate": (
                    datetime.now() - timedelta(days=1825)).strftime("%d/%m/%Y")
            }
        )
        return self

    @classmethod
    async def create_via_login_existing_device(cls,
                                               email: str,
                                               password: str,
                                               dev_id: str):
        """Create a login via existing device details."""
        self = cls()
        self.username = email
        self._password = password
        self.device_id = dev_id
        await self.refresh_login()
        return self

    async def refresh_login(self):
        """Updates the access token and logs back in."""
        resp = await self.send_request(
            endpoint="login",
            body={
                "DeviceId": self.device_id,
                "Password": self._password,
                "RememberMe": True,
                "UserName": self.username
            })
        self.access_token = resp["Data"][0]["AuthToken"]
        #self.ts = round((datetime.now() + timedelta(days=5)).timestamp() / 10, 0)
        self.ts = 171260490
        self.primary_bp_number = resp["Data"][0]["PrimaryBPNumber"]
        self.account_number = resp["Data"][0]["PrimaryAccountNumber"]
        if self.next_refresh is None:
            self.next_refresh = datetime.now()+timedelta(minutes=30)
        else:
            self.next_refresh += timedelta(minutes=30)

    async def send_request(self, endpoint: str, body: dict) -> dict:
        """Send a request to the API, and return the JSON response."""
        if endpoint not in API_ENDPOINTS:
            raise ValueError("Provided API Endpoint does not exist.")

        endpoint_map = API_ENDPOINTS[endpoint]
        headers = {
            "ApplicationKey": API_APP_KEY,
            "Partnerkey": self.generate_partner_key()
        }
        if self.access_token is not None:
            headers["Authorization"] = self.access_token

        if endpoint != "login" and self.next_refresh <= datetime.now():
            _LOGGER.debug(">> Refreshing access token.")
            await self.refresh_login()

        if self.access_token is None and endpoint != "login":
            raise ExpiredAccessTokenError()

        async with aiohttp.ClientSession() as _session:
            async with _session.request(
                method=endpoint_map["method"],
                url=API_BASEURL + endpoint_map["endpoint"],
                headers=headers,
                json=body
            ) as _response:
                if not _response.ok:
                    _LOGGER.error(">> Error sending request %s to Anglian Water (%s) - %s",
                                  endpoint,
                                  _response.status,
                                  await _response.text())
                    if _response.status == 401:
                        self.access_token = None
                        raise ExpiredAccessTokenError()
                # Check StatusCode in response body.
                resp_body = await _response.json()
                if resp_body["StatusCode"] == "0":
                    # Successful request
                    _LOGGER.debug(">> Request to %s successful.", endpoint)
                    return resp_body
                if resp_body["StatusCode"] in API_RESPONSE_STATUS_CODE_MAPPING:
                    raise API_RESPONSE_STATUS_CODE_MAPPING[resp_body["StatusCode"]]
                raise UnknownEndpointError(resp_body)
