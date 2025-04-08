"""Generic utilities to help with authentication."""

import random
import hashlib
import base64
import urllib.parse
import logging
import inspect

_LOGGER = logging.getLogger(__name__)

def is_awaitable(func):
    """
    Check if a function is awaitable.

    Args:
        func: The function to check.

    Returns:
        True if the function is awaitable, False otherwise.
    """
    return inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)

def random_string(lower_bound: int, higher_bound: int) -> str:
    """
    Generates a random string of alphanumeric characters, hyphens, and underscores.

    Args:
        lower_bound: The minimum length of the string.
        higher_bound: The maximum length of the string.

    Returns:
        A random string.
    """
    valid = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
    chars = random.randint(lower_bound, higher_bound)
    random_string_builder = ''
    for _ in range(chars):  # Use _ as a placeholder for unused loop variable
        random_string_builder += random.choice(valid)
    return random_string_builder

def build_code_challenge(code_verify: str) -> str:
    """
    Generates a code challenge from a code verifier.

    Args:
        code_verify: The code verifier string.

    Returns:
        The code challenge string.
    """
    return hash_data(code_verify).replace('+', '-').replace('/', '_').replace('=', '')

def hash_data(data: str) -> str:
    """
    Hashes the input data string using SHA-256 and encodes the result in Base64.

    Args:
        data: The string to hash.

    Returns:
        The Base64 encoded SHA-256 hash of the data string.
    """
    # Create a SHA-256 hash
    hashed = hashlib.sha256(data.encode('utf-8')).digest()
    return base64.b64encode(hashed).decode('utf-8')

def decode_oauth_redirect(redir_url: str):
    """Decodes the OAuth redirect URL and extracts the code and state."""
    try:
        parsed_uri = urllib.parse.urlparse(redir_url)
        query_params = urllib.parse.parse_qs(parsed_uri.query)
        state = query_params.get("state", [None])[0]
        code_encoded = query_params.get("code", [None])[0]
        if code_encoded:
            return state, code_encoded
        else:
            _LOGGER.error("Code not found in redirect URI")
            return None
    except(ValueError, TypeError) as e:
        _LOGGER.exception("Error decoding redirect URI: %s", e, exc_info=e)
        return None
