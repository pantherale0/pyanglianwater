"""Unit tests for pyanglianwater.utils module."""

import pytest
import jwt

from pyanglianwater.utils import (
    is_awaitable,
    random_string,
    build_code_challenge,
    hash_data,
    decode_oauth_redirect,
    encrypt_string_to_charcode_hex,
    decode_jwt,
)


def test_is_awaitable():
    """Test that is_awaitable correctly identifies async and sync functions."""
    async def async_func():
        pass

    def sync_func():
        pass

    assert is_awaitable(async_func) is True
    assert is_awaitable(sync_func) is False


def test_random_string():
    """Test that random_string generates strings within specified length range."""
    result = random_string(5, 10)
    assert 5 <= len(result) <= 10
    assert all(c.isalnum() or c in "-_" for c in result)


def test_build_code_challenge():
    """Test that build_code_challenge generates a valid code challenge."""
    code_verifier = "test_verifier"
    challenge = build_code_challenge(code_verifier)
    assert isinstance(challenge, str)
    assert len(challenge) > 0


def test_hash_data():
    """Test that hash_data produces a non-empty hash string."""
    data = "test_data"
    hashed = hash_data(data)
    assert isinstance(hashed, str)
    assert len(hashed) > 0


def test_decode_oauth_redirect():
    """Test that decode_oauth_redirect extracts state and code from URLs."""
    url = "https://example.com/callback?state=test_state&code=test_code"
    state, code = decode_oauth_redirect(url)
    assert state == "test_state"
    assert code == "test_code"

    invalid_url = "https://example.com/callback"
    result = decode_oauth_redirect(invalid_url)
    assert result is None


def test_encrypt_string_to_charcode_hex():
    """Test that encrypt_string_to_charcode_hex encodes strings and validates input types."""
    plaintext = "test_string"
    encrypted = encrypt_string_to_charcode_hex(plaintext)
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0

    with pytest.raises(TypeError):
        encrypt_string_to_charcode_hex(12345)


def test_decode_jwt():
    """Test that decode_jwt decodes valid tokens and handles invalid ones gracefully."""
    token = jwt.encode({"key": "value"}, "secret", algorithm="HS256")
    decoded = decode_jwt(token)
    assert decoded.get("key") == "value"

    invalid_token = "invalid.token"
    decoded = decode_jwt(invalid_token)
    assert decoded == {}
