"""Exceptions for Anglian Water."""

class AuthError(Exception):
    """General authentication error."""

class UnknownEndpointError(Exception):
    """Defines an unknown error."""

class ExpiredAccessTokenError(AuthError):
    """401 Unauthorized"""

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
