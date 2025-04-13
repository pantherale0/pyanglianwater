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
    AW_APP_ENDPOINTS,
    AW_APP_BASEURL,
    AW_TARIFF_URL
)
from .exceptions import (
    ExpiredAccessTokenError,
    UnknownEndpointError,
    InvalidAccountIdError,
    SelfAssertedError
)
from .utils import (
    random_string,
    build_code_challenge,
    decode_oauth_redirect,
    encrypt_string_to_charcode_hex,
    decode_jwt
)

_LOGGER = logging.getLogger(__name__)

class BaseAuth:
    """Base authentication methods."""
    _auth_session: aiohttp.ClientSession | None = None
    access_token: str = None
    username: str = None
    _password: str = None
    _account_number: str = None
    next_refresh: datetime = None

    def __init__(self, username, password, session=None, refresh_token=None, account_number=None):
        if session:
            self._auth_session = session
        else:
            self._auth_session = aiohttp.ClientSession()
        self.username = username
        self._password = password
        self._refresh_token = refresh_token
        self._account_number = account_number

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

    async def send_request(self, endpoint: str, body: dict, **kwargs):
        """Send a request to an API."""
        raise NotImplementedError("Function not available.")

    async def get_tariff_data(self) -> dict:
        """Retrieve tariff data from GitHub."""
        response = await self._auth_session.get(AW_TARIFF_URL)
        if response.ok:
            return json.loads(await response.text())
        _LOGGER.error("Failed to retrieve tariff data: %s", response.status)

class MSOB2CAuth(BaseAuth):
    """Represent an instance of MSO Auth."""
    _pkce_verifier = random_string(43,128)
    _pkce_challenge = None
    _state = secrets.token_urlsafe(32)
    _csrf_token: str = ""
    _cookie_cache: dict = {}
    _decoded_access_token: dict = {}
    auth_data: dict = None

    @property
    def account_number(self) -> str:
        """Return the account id."""
        if self._account_number is not None:
            return encrypt_string_to_charcode_hex(self._account_number)
        return encrypt_string_to_charcode_hex(
            self._decoded_access_token.get("extension_defaultAccountNumber", "")
        )

    @property
    def access_token(self) -> str:
        """Return the access token."""
        if self.auth_data is None:
            return None
        return self.auth_data.get("access_token")

    @property
    def refresh_token(self) -> str:
        """Return the access token."""
        if self._refresh_token is not None:
            return self._refresh_token
        if self.auth_data is None:
            return None
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
        _LOGGER.debug("B2C Auth: Getting initial auth data")
        self._state = secrets.token_urlsafe(32)
        self._pkce_challenge = build_code_challenge(self._pkce_verifier)
        auth_response = await self._auth_session.get(
            AUTH_MSO_STEP_1_URL.format(
                CODE_CHALLENGE=self._pkce_challenge,
                EMAIL=self.username,
                STATE=self._state
            ),
            allow_redirects=False
        )

        if not auth_response.ok:
            data = await auth_response.text()
            _LOGGER.error("B2C Auth: Initial Authorization URL request failed %s: %s",
                          auth_response.status, data)
            return None

        if auth_response.status == 302:
            location = auth_response.headers.get("Location")
            if not location:
                _LOGGER.error("B2C Auth: Location header not found")
                return None
            return location

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
        _LOGGER.debug("B2C Auth: Submitting self-asserted form")
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
        status = int(data.get("status"))
        if asserted_login_response.status != 200 or status != 200:
            _LOGGER.error("B2C Auth: SelfAsserted request failed %s: %s",
                          asserted_login_response.status,
                          data)
            if status == 400:
                raise SelfAssertedError(
                    f'{data.get("errorCode", "Unknown")} {data.get("message", "Unknown")}'
                )
            return None

        return asserted_login_response

    async def _get_confirmation_redirect(self):
        """Gets the confirmation redirect URL."""
        _LOGGER.debug("B2C Auth: Getting confirmation redirect URL")
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
        _LOGGER.debug("B2C Auth: Getting access token from authorization code")
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

    async def send_refresh_request(self):
        """Send a request to refresh the access token."""
        _LOGGER.debug("B2C Auth: Refreshing access token")
        if self.access_token is None and self.refresh_token is None:
            raise ValueError("Not logged in.")
        if self.next_refresh is not None:
            if self.next_refresh > datetime.now():
                _LOGGER.debug("B2C Auth: Access token not yet expired")
                return
        token_request_response = await self._auth_session.post(
            AUTH_MSO_GET_TOKEN_URL,
            data=urllib.parse.urlencode(
                {
                    "grant_type": "refresh_token",
                    "client_id": AUTH_MSO_CLIENT_ID,
                    "refresh_token": self.refresh_token,
                }
            ),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": AW_APP_USER_AGENT,
            },
        )

        if token_request_response.status != 200:
            text = await token_request_response.text()
            _LOGGER.error("B2C Auth: Refresh token request failed %s: %s",
                          token_request_response.status, text)
            return None

        try:
            token_data = await token_request_response.json()
            self.auth_data = token_data
            self.next_refresh = datetime.now()+timedelta(seconds=token_data["expires_in"])
            self._decoded_access_token = decode_jwt(self.access_token)
            _LOGGER.debug("B2C Auth: Access token refreshed successfully, new expiration time: %s",
                          self.next_refresh)
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            _LOGGER.error("B2C Auth: Error processing refresh response: %s", e)

    async def send_login_request(self):
        """Send a request to MSO for Auth."""
        if self._refresh_token is not None:
            _LOGGER.debug("B2C Auth: Using refresh token for authentication")
            # Attempt to use refresh token first
            try:
                await self.send_refresh_request()
                return
            except Exception as e:
                _LOGGER.warning("B2C Auth: Refresh token failed, falling back to initial login: %s", e)
        auth_data = await self._get_initial_auth_data()
        if auth_data is None:
            return
        if isinstance(auth_data, tuple):
            self._csrf_token, trans_id = auth_data
            asserted_response = await self._submit_self_asserted_form(trans_id)
            if asserted_response is None:
                return
            redirect_location = await self._get_confirmation_redirect()
            if redirect_location is None:
                return
        elif "uk.co.anglianwater.myaccount://" in auth_data:
            redirect_location = auth_data
        _, code = decode_oauth_redirect(redirect_location)
        if not code:
            _LOGGER.error("B2C Auth: Code not found")
            return

        token_response = await self._get_token(code)
        if token_response is None:
            _LOGGER.error("B2C Auth: Token request failed")
            return

        self.auth_data = token_response
        self.next_refresh = datetime.now()+timedelta(seconds=token_response["expires_in"])
        self._refresh_token = token_response.get("refresh_token")
        self._decoded_access_token = decode_jwt(self.access_token)
        _LOGGER.debug("B2C Auth: Access token obtained successfully, new expiration time: %s", self.next_refresh)

    async def send_request(self, endpoint: str, body: dict, **kwargs) -> dict:
        """Send a request to the API, and return the JSON response."""
        if endpoint not in AW_APP_ENDPOINTS:
            raise ValueError("Provided API Endpoint does not exist.")


        _LOGGER.debug("Sending request to %s", endpoint)
        endpoint_map = AW_APP_ENDPOINTS[endpoint]
        await self.send_refresh_request()
        if self.access_token is None:
            _LOGGER.debug("Access token unavailable, not logged in.")
            raise ExpiredAccessTokenError()
        headers = self.get_authenticated_headers
        built_url = AW_APP_BASEURL + endpoint_map["endpoint"].format(ACCOUNT_ID=self.account_number, **kwargs)
        async with aiohttp.ClientSession() as _session:
            async with _session.request(
                method=endpoint_map["method"],
                url=built_url,
                headers=headers,
                json=body
            ) as _response:
                _LOGGER.debug("Request to %s returned with status %s", built_url, _response.status)
                if _response.ok and _response.content_type == "application/json":
                    return await _response.json()
                if _response.status == 401:
                    raise ExpiredAccessTokenError()
                if _response.status == 403:
                    raise InvalidAccountIdError()
                raise UnknownEndpointError(_response.status, await _response.text())
