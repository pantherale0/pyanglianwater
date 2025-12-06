"""Authentication and API handling for Anglian Water."""

import logging

from .auth import MSOB2CAuth
from .const import AW_APP_BASEURL, AW_APP_ENDPOINTS
from .utils import encrypt_string_to_charcode_hex

_LOGGER = logging.getLogger(__name__)


class API:
    """API Handler for Anglian Water."""

    def __init__(self, auth_obj: MSOB2CAuth):
        self._auth = auth_obj

    @property
    def username(self):
        """Get username from auth."""
        return self._auth.username

    async def send_request(
        self, endpoint: str, body: dict | None, account_number: str, **kwargs
    ):
        """Send a request to the API using the authentication handler."""
        if endpoint not in AW_APP_ENDPOINTS:
            raise ValueError("Provided API Endpoint does not exist.")
        _LOGGER.debug(
            "API: Sending request to endpoint '%s' with body: %s", endpoint, body
        )
        endpoint_map = AW_APP_ENDPOINTS[endpoint]
        built_url = AW_APP_BASEURL + endpoint_map["endpoint"].format(
            ACCOUNT_ID=encrypt_string_to_charcode_hex(account_number),
            BUSINESS_PARTNER_ID=encrypt_string_to_charcode_hex(
                self._auth.business_partner_number
            ),
            **kwargs,
        )
        return await self._auth.send_request(
            method=endpoint_map["method"],
            url=built_url,
            body=body,
            headers=self._auth.authenticated_headers,
        )

    async def get_associated_accounts(self, account_number: str):
        """Get associated accounts."""
        return await self.send_request(
            endpoint="get_associated_accounts", body=None, account_number=account_number
        )

    async def token_refresh(self):
        """Force token refresh."""
        return await self._auth.send_refresh_request()

    async def login(self):
        """Login to the API."""
        return await self._auth.send_login_request()

    def to_dict(self) -> dict:
        """Returns the API object data as a dictionary."""
        return {
            "username": self.username,
            "next_refresh": self._auth.next_refresh,
        }

    def __iter__(self):
        """Allows the object to be converted to a dictionary using dict()."""
        return iter(self.to_dict().items())
