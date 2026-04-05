"""Exceptions for Anglian Water."""


class AuthError(Exception):
    """General authentication error."""


class HttpException(Exception):
    """General HTTP error storing status and response."""

    def __init__(self, status: int, response: str):
        self.status = status
        self.response = response
        super().__init__(f"HTTP {status}: {response}")


class UnknownEndpointError(HttpException):
    """Defines an unknown error."""


class ExpiredAccessTokenError(AuthError):
    """401 Unauthorized"""


class InvalidGrantError(AuthError):
    """400 Grant expired error."""


class InvalidRequestError(AuthError):
    """OAuth request is malformed or missing required parameters."""


class InvalidClientError(AuthError):
    """Client authentication failed."""


class UnauthorizedClientError(AuthError):
    """Client is not authorized for this grant type or flow."""


class UnsupportedGrantTypeError(AuthError):
    """OAuth grant type is not supported."""


class InvalidScopeError(AuthError):
    """Requested OAuth scope is invalid, unknown, or malformed."""


class AccessDeniedError(AuthError):
    """Resource owner or policy denied the request."""


class InteractionRequiredError(AuthError):
    """Interactive user action is required to continue."""


class LoginRequiredError(AuthError):
    """User sign-in is required to continue."""


class ConsentRequiredError(AuthError):
    """User/admin consent is required to continue."""


class TemporarilyUnavailableError(AuthError):
    """Authorization server is temporarily unavailable."""


class ServiceUnavailableError(Exception):
    """503 Service Unavailable."""


class TariffNotAvailableError(Exception):
    """Tariff information not available or set."""


class SmartMeterUnavailableError(Exception):
    """Smart meter not available."""


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
