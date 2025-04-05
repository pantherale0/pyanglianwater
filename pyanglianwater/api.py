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

    async def send_request(self, endpoint: str, body: dict):
        """Send a request to the API using the authentication handler."""
        return await self._auth.send_request(endpoint=endpoint, body=body)
