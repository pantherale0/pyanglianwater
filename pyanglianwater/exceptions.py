"""Exceptions for Anglian Water."""

class InvalidPasswordError(Exception):
    """E_LGN_006"""

class InvalidUsernameError(Exception):
    """E_LGN_008"""

class EndpointUnavailableError(Exception):
    """S_SMR_1058"""

class UnknownEndpointError(Exception):
    """Defines an unknown error."""

class ExpiredAccessTokenError(Exception):
    """401 Unauthorized"""

class ServiceUnavailableError(Exception):
    """503 Service Unavailable."""

class TariffNotAvailableError(Exception):
    """Tariff information not available or set."""

API_RESPONSE_STATUS_CODE_MAPPING = {
    "E_LGN_006": InvalidPasswordError,
    "E_LGN_008": InvalidUsernameError,
    "S_SMR_1058": EndpointUnavailableError
}
