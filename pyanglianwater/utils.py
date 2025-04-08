"""Generic utilities to help with encryption and authorization."""

import os
import random
import hashlib
import base64
import urllib.parse
import logging
import inspect

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as sym_padding

import jwt

from .const import (
    AW_ENCRYPTION_KEY,
    AW_ENCRYPTION_ITERATIONS,
    AW_ENCRYPTION_PBKDF2_HASH,
    AW_ENCRYPTION_SALT_SIZE,
    AW_ENCRYPTION_IV_SIZE,
    AW_ENCRYPTION_KEY_SIZE,
)

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

### ENCRYPTION RELATED FUNCTIONS ###

def _derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 256-bit key using PBKDF2-HMAC-SHA1."""
    password_bytes = password.encode('utf-8')
    key = hashlib.pbkdf2_hmac(
        AW_ENCRYPTION_PBKDF2_HASH,
        password_bytes,
        salt,
        AW_ENCRYPTION_ITERATIONS,
        dklen=AW_ENCRYPTION_KEY_SIZE
    )
    return key

def _convert_string_to_char_code_hex(input_str: str) -> str:
    """Converts a string to the hex representation of its char codes."""
    return ''.join(hex(ord(char))[2:].zfill(2) for char in input_str)

def encrypt_string_to_charcode_hex(plaintext_string: str) -> str:
    """Encrypts a string using AES encryption and returns the result as a char-code-hex string."""
    if not isinstance(plaintext_string, str):
        raise TypeError("Input must be a string.")

    # 1. Generate random Salt and IV for each encryption
    salt = os.urandom(AW_ENCRYPTION_SALT_SIZE)
    iv = os.urandom(AW_ENCRYPTION_IV_SIZE)

    # 2. Derive the encryption key from the key and salt
    key = _derive_key(AW_ENCRYPTION_KEY, salt)

    # 3. Prepare AES cipher
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    # 4. Encode the input string and apply PKCS7 padding
    padder = sym_padding.PKCS7(algorithms.AES.block_size).padder()
    plaintext_bytes = plaintext_string.encode('utf-8')
    padded_data = padder.update(plaintext_bytes) + padder.finalize()

    # 5. Encrypt
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    # 6. Concatenate salt, iv, and ciphertext
    encrypted_bundle_bytes = salt + iv + ciphertext

    # 7. Encode the raw byte bundle to Base64
    base64_encoded_bundle = base64.b64encode(encrypted_bundle_bytes).decode('ascii')

    # 8. Convert the Base64 string itself to char-code-hex
    charcode_hex_output = _convert_string_to_char_code_hex(base64_encoded_bundle)

    return charcode_hex_output

### JWT FUNCTIONS ###

def decode_jwt(token: str) -> dict:
    """Decode a given JWT into a dict."""
    try:
        decoded = jwt.decode(
            token,
            options={"verify_signature": False}
        )
        return decoded
    except jwt.DecodeError as e:
        _LOGGER.error("Failed to decode JWT: %s", e)
        return {}
