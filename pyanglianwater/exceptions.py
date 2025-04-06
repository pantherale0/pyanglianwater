"""Exceptions for Anglian Water."""

class LegacyAuthError(Exception):
    """General authentication error for legacy authentication."""

class AuthError(Exception):
    """General authentication error."""

class InvalidPasswordError(LegacyAuthError):
    """E_LGN_006"""

class InvalidUsernameError(LegacyAuthError):
    """E_LGN_008"""

class EndpointUnavailableError(LegacyAuthError):
    """S_SMR_1058"""

class UnknownEndpointError(Exception):
    """Defines an unknown error."""

class ExpiredAccessTokenError(LegacyAuthError):
    """401 Unauthorized"""

class ServiceUnavailableError(Exception):
    """503 Service Unavailable."""

class TariffNotAvailableError(Exception):
    """Tariff information not available or set."""

class InitialAuthError(AuthError):
    """Error requesting auth configuration."""
class SelfAssertedError(AuthError):
    """Error performing login via username and password."""
class ConfirmationRedirectError(AuthError):
    """Error confirming login with redirect."""
class TokenRequestError(AuthError):
    """Error requesting a token from the token server."""

class InvalidAccountIdError(AuthError):
    """403 Invalid account ID."""

API_RESPONSE_STATUS_CODE_MAPPING = {
    "E_LGN_006": InvalidPasswordError,
    "E_LGN_008": InvalidUsernameError,
    "S_SMR_1058": EndpointUnavailableError
}
