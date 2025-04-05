"""Authentication handlers."""

import secrets
import urllib.parse
import re
import logging
import json

from datetime import datetime, timedelta

import aiohttp

from .const import (
    AUTH_MSO_STEP_1_URL,
    AUTH_MSO_SELF_ASSERTED_URL,
    AUTH_MSO_GET_TOKEN_URL,
    AUTH_AW_BASE,
    AUTH_MSO_CONFIRM_URL,
    AUTH_MSO_CLIENT_ID,
    AUTH_MSO_REDIR_URI,
    AW_APP_USER_AGENT,
    API_LEGACY_PARTNER_KEY,
    API_LEGACY_APP_KEY,
    AUTH_LEGACY_URL,
    LEGACY_API_ENDPOINTS,
    LEGACY_API_BASEURL,
    AW_APP_ENDPOINTS,
    AW_APP_BASEURL
)
from .exceptions import (
    API_RESPONSE_STATUS_CODE_MAPPING,
    ExpiredAccessTokenError,
    UnknownEndpointError,
    ServiceUnavailableError
)
from .utils import random_string, build_code_challenge, decode_oauth_redirect

_LOGGER = logging.getLogger(__name__)

class BaseAuth:
    """Base authentication methods."""
    _auth_session: aiohttp.ClientSession | None = None
    access_token: str = None
    username: str = None
    _password: str = None
    account_number: str = None
    primary_bp_number: str = None
    next_refresh: datetime = None
    device_id: str = None

    def __init__(self, username, password, session=None, device_id=None, account_id=None):
        if session:
            self._auth_session = session
        else:
            self._auth_session = aiohttp.ClientSession()
        self.username = username
        self._password = password
        self.device_id = device_id
        self.account_number = account_id

    async def send_refresh_request(self):
        """Send a authenticated refresh request."""
        if self.access_token is None:
            raise ValueError("Not logged in.")
        if self.next_refresh > datetime.now():
            return
        await self.send_login_request()

    async def send_login_request(self):
        """Send a unauthenticated initial login request."""
        if self.access_token is not None:
            raise ValueError("Already logged in. Use refresh instead.")

    async def send_request(self, endpoint: str, body: dict):
        """Send a request to an API."""
        raise NotImplementedError("Function not available.")

class LegacyAuth(BaseAuth):
    """Legacy mobile authentication handler."""
    _new_device = True

    def __init__(self, username, password, session=None, device_id=None):
        super().__init__(username, password, session, device_id)
        if device_id is not None:
            self._new_device = False
        else:
            self.device_id = secrets.token_hex(8)
            _LOGGER.debug(
                ">> Generated device ID %s. Keep this safe to login to this session in the future.",
            self.device_id)

    def generate_partner_key(self):
        """Generate a partner key for authentication."""
        if self.access_token is None:
            return API_LEGACY_PARTNER_KEY.format(
                EMAIL="undefined",
                ACC_NO="undefined",
                DEV_ID=self.device_id,
                APP_KEY=API_LEGACY_APP_KEY
            )
        return API_LEGACY_PARTNER_KEY.format(
                EMAIL=self.username,
                ACC_NO=self.account_number,
                DEV_ID=self.device_id,
                APP_KEY=API_LEGACY_APP_KEY
            )

    def parse_login_response(self, response):
        """Parse a login request response."""
        self.access_token = response["Data"][0]["AuthToken"]
        self.primary_bp_number = response["Data"][0]["ActualBPNumber"]
        self.account_number = response["Data"][0]["ActualAccountNo"]
        # set a low refresh interval to ensure we reload properly
        if self.next_refresh is None:
            self.next_refresh = datetime.now()+timedelta(minutes=15)
        else:
            self.next_refresh += timedelta(minutes=15)

    async def send_request(self, endpoint: str, body: dict) -> dict:
        """Send a request to the API, and return the JSON response."""
        if endpoint not in LEGACY_API_ENDPOINTS:
            raise ValueError("Provided API Endpoint does not exist.")

        endpoint_map = LEGACY_API_ENDPOINTS[endpoint]
        headers = {
            "ApplicationKey": API_LEGACY_APP_KEY,
            "Partnerkey": self.generate_partner_key()
        }
        if self.access_token is not None:
            headers["Authorization"] = self.access_token
        await self.send_refresh_request()
        if self.access_token is None:
            raise ExpiredAccessTokenError()

        async with aiohttp.ClientSession() as _session:
            async with _session.request(
                method=endpoint_map["method"],
                url=LEGACY_API_BASEURL + endpoint_map["endpoint"],
                headers=headers,
                json=body
            ) as _response:
                if not _response.ok:
                    if _response.status == 401:
                        # refresh access token
                        await self.send_refresh_request()
                        # retry sending request
                        return await self.send_request(endpoint, body)
                    if _response.status == 503:
                        self.access_token = None
                        raise ServiceUnavailableError()
                    _LOGGER.error(">> Error sending request %s to Anglian Water (%s) - %s",
                                  endpoint,
                                  _response.status,
                                  await _response.text())
                # Check StatusCode in response body.
                if _response.content_type != "application/json":
                    raise UnknownEndpointError(await _response.text())
                resp_body = await _response.json()
                if resp_body["StatusCode"] == "0":
                    # Successful request
                    _LOGGER.debug(">> Request to %s successful.", endpoint)
                    return resp_body
                if resp_body["StatusCode"] in API_RESPONSE_STATUS_CODE_MAPPING:
                    raise API_RESPONSE_STATUS_CODE_MAPPING[resp_body["StatusCode"]]
                raise UnknownEndpointError(resp_body)

    async def send_new_registration_queries(self):
        """Send new device registration queries."""
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
                "Vkont": str(self.account_number)
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
                "Vkont": str(self.account_number)
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

    async def send_login_request(self):
        """Send a login request to the legacy endpoints."""
        resp = await self._auth_session.request(
            "POST",
            url=AUTH_LEGACY_URL,
            json={
                "DeviceId": self.device_id,
                "Password": self._password,
                "RememberMe": True,
                "UserName": self.username
            }
        )
        self.parse_login_response(resp)

class MSOB2CAuth(BaseAuth):
    """Represent an instance of MSO Auth."""
    _pkce_verifier = random_string(43,128)
    _pkce_challenge = None
    _state = secrets.token_urlsafe(32)
    _csrf_token: str = ""
    _cookie_cache: dict = {}
    auth_data: dict = None

    @property
    def access_token(self) -> str:
        """Return the access token."""
        return self.auth_data.get("access_token")

    @property
    def refresh_token(self) -> str:
        """Return the access token."""
        return self.auth_data.get("refresh_token")

    @property
    def get_authenticated_headers(self) -> dict:
        """Return authenticated headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Ocp-Apim-Subscription-Key": "adbc43b29a87404cbc297fe6d7a3d10e",
            "Accept": "application/json",
            "User-Agent": AW_APP_USER_AGENT
        }

    async def _get_initial_auth_data(self):
        """Retrieves initial authentication data (CSRF token, transId)."""
        self._state = secrets.token_urlsafe(32)
        self._pkce_challenge = build_code_challenge(self._pkce_verifier)
        auth_response = await self._auth_session.get(
            AUTH_MSO_STEP_1_URL.format(
                CODE_CHALLENGE=self._pkce_challenge,
                EMAIL=self.username,
                STATE=self._state
            )
        )

        if not auth_response.ok:
            data = await auth_response.text()
            _LOGGER.error("B2C Auth: Initial Authorization URL request failed %s: %s",
                          auth_response.status, data)
            return None

        html = await auth_response.text()
        match = re.search(r"var SETTINGS = {([^;]+)};", html)
        if not match:
            _LOGGER.error("B2C Auth: SETTINGS object not found in HTML")
            return None

        settings_json_str = match.group(1)
        csrf_match = re.search(r'"csrf":\s*"([^"]+)"', settings_json_str)
        trans_id_match = re.search(r'"transId":\s*"([^"]+)"', settings_json_str)

        if not csrf_match or not trans_id_match:
            _LOGGER.error("B2C Auth: CSRF or Transaction ID not found in SETTINGS")
            return None

        _csrf_token = csrf_match.group(1)
        trans_id = trans_id_match.group(1)

        _LOGGER.debug("Got CSRF %s and Transaction ID %s", _csrf_token, trans_id)

        return _csrf_token, trans_id

    async def _submit_self_asserted_form(self, trans_id):
        """Submits the SelfAsserted form."""
        data = {
            "request_type":"RESPONSE",
            "email": self.username,
            "password": self._password
        }
        asserted_login_response = await self._auth_session.post(
            AUTH_MSO_SELF_ASSERTED_URL.format(STATE=trans_id),
            headers={
                "X-CSRF-TOKEN": self._csrf_token,
                "Referer": AUTH_MSO_STEP_1_URL.format(
                    CODE_CHALLENGE=self._pkce_challenge,
                    EMAIL=self.username,
                    STATE=self._state
                ),
                "Origin": AUTH_AW_BASE,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": AW_APP_USER_AGENT,
            },
            data=data,
        )
        data = await asserted_login_response.json(content_type="text/json")
        if asserted_login_response.status != 200 or int(data["status"]) != 200:
            _LOGGER.error("B2C Auth: SelfAsserted request failed %s: %s",
                          asserted_login_response.status,
                          data)
            return None

        return asserted_login_response

    async def _get_confirmation_redirect(self):
        """Gets the confirmation redirect URL."""
        confirm_login_response = await self._auth_session.get(
            AUTH_MSO_CONFIRM_URL.format(CSRF=self._csrf_token, STATE=self._state),
            allow_redirects=False
        )

        if confirm_login_response.status != 302:
            text = await confirm_login_response.text()
            _LOGGER.error("B2C Auth: Confirm request failed %s: %s",
                          confirm_login_response.status, text)
            return None

        location = confirm_login_response.headers.get("Location")
        if not location:
            _LOGGER.error("B2C Auth: Location header not found")
            return None

        return location

    async def _get_token(self, code):
        """Requests the access token."""
        token_request_response = await self._auth_session.post(
            AUTH_MSO_GET_TOKEN_URL,
            data=urllib.parse.urlencode(
                {
                    "grant_type": "authorization_code",
                    "client_id": AUTH_MSO_CLIENT_ID,
                    "redirect_uri": AUTH_MSO_REDIR_URI,
                    "code": code,
                    "code_verifier": self._pkce_verifier,
                }
            ),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": AW_APP_USER_AGENT,
            },
        )

        if token_request_response.status != 200:
            text = await token_request_response.text()
            _LOGGER.error("B2C Auth: Token request failed %s: %s",
                          token_request_response.status, text)
            return None

        try:
            token_data = await token_request_response.json()
            return token_data
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            _LOGGER.error("B2C Auth: Error processing token response: %s", e)
            return None

    async def send_login_request(self):
        """Send a request to MSO for Auth."""
        auth_data = await self._get_initial_auth_data()
        if auth_data is None:
            return
        self._csrf_token, trans_id = auth_data
        asserted_response = await self._submit_self_asserted_form(trans_id)
        if asserted_response is None:
            return
        redirect_location = await self._get_confirmation_redirect()
        if redirect_location is None:
            return

        _, code = decode_oauth_redirect(redirect_location)
        if not code:
            _LOGGER.error("B2C Auth: Code not found")
            return

        token_response = await self._get_token(code)
        if token_response is None:
            return

        self.auth_data = token_response
        self.next_refresh = datetime.now()+timedelta(seconds=token_response["expires_in"])

    async def send_request(self, endpoint: str, body: dict) -> dict:
        """Send a request to the API, and return the JSON response."""
        if endpoint not in AW_APP_ENDPOINTS:
            raise ValueError("Provided API Endpoint does not exist.")


        _LOGGER.debug("Sending request to %s", endpoint)
        endpoint_map = AW_APP_ENDPOINTS[endpoint]
        headers = self.get_authenticated_headers
        await self.send_refresh_request()
        if self.access_token is None:
            _LOGGER.debug("Access token unavailable, not logged in.")
            raise ExpiredAccessTokenError()

        async with aiohttp.ClientSession() as _session:
            async with _session.request(
                method=endpoint_map["method"],
                url=AW_APP_BASEURL + endpoint_map["endpoint"].format(ACCOUNT_ID=self.account_number),
                headers=headers,
                json=body
            ) as _response:
                _LOGGER.debug("Request to %s returned with status %s", endpoint, _response.status)
                if _response.ok and _response.content_type == "application/json":
                    return await _response.json()
                if _response.status == 401 or _response.status == 403:
                    raise ExpiredAccessTokenError()
                raise UnknownEndpointError(_response.status, await _response.text())
