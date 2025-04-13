"""Authentication and API handling for Anglian Water."""

import logging

from .auth import BaseAuth

_LOGGER = logging.getLogger(__name__)

class API:
    """API Handler for Anglian Water."""

    def __init__(self, auth_obj: BaseAuth):
        self._auth = auth_obj

    @property
    def account_number(self):
        """Get account number."""
        return self._auth.account_number

    @property
    def primary_bp_number(self):
        """Get connection number."""
        return self._auth.primary_bp_number

    @property
    def username(self):
        """Get username from auth."""
        return self._auth.username

    async def send_request(self, endpoint: str, body: dict, **kwargs):
        """Send a request to the API using the authentication handler."""
        return await self._auth.send_request(endpoint=endpoint, body=body, **kwargs)

    async def load_tariff_data(self) -> dict:
        """Load tariff data from GitHub."""
        return await self._auth.get_tariff_data()

    async def token_refresh(self):
        """Force token refresh."""
        return await self._auth.send_refresh_request()

    async def login(self):
        """Login to the API."""
        return await self._auth.send_login_request()

    def to_dict(self) -> dict:
        """Returns the API object data as a dictionary."""
        return {
            "account_number": self.account_number,
            "username": self.username,
            "next_refresh": self._auth.next_refresh
        }

    def __iter__(self):
        """Allows the object to be converted to a dictionary using dict()."""
        return iter(self.to_dict().items())
