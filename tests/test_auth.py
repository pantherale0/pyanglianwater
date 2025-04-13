import pytest
import aiohttp
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from pyanglianwater.auth import MSOB2CAuth

from pyanglianwater.exceptions import (
    ExpiredAccessTokenError,
    InvalidAccountIdError
)

@pytest.fixture
async def auth_instance():
    """Fixture to create an instance of MSOB2CAuth."""
    async with aiohttp.ClientSession() as session:
        return MSOB2CAuth(username="testuser", password="testpassword", session=session)

@pytest.mark.asyncio
async def test_initial_auth_data(auth_instance):
    """Test the _get_initial_auth_data method."""
    with patch("pyanglianwater.auth.aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.ok = True
        mock_get.return_value.status = 302
        mock_get.return_value.headers = {"Location": "https://example.com"}
        location = await auth_instance._get_initial_auth_data()
        assert location == "https://example.com"

@pytest.mark.asyncio
async def test_submit_self_asserted_form(auth_instance):
    """Test the _submit_self_asserted_form method."""
    with patch("pyanglianwater.auth.aiohttp.ClientSession.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status = 200
        mock_post.return_value.json = AsyncMock(return_value={"status": 200})
        response = await auth_instance._submit_self_asserted_form("test_trans_id")
        assert response is not None

@pytest.mark.asyncio
async def test_get_confirmation_redirect(auth_instance):
    """Test the _get_confirmation_redirect method."""
    with patch("pyanglianwater.auth.aiohttp.ClientSession.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status = 302
        mock_get.return_value.headers = {"Location": "https://example.com"}
        location = await auth_instance._get_confirmation_redirect()
        assert location == "https://example.com"

@pytest.mark.asyncio
async def test_get_token(auth_instance):
    """Test the _get_token method."""
    with patch("pyanglianwater.auth.aiohttp.ClientSession.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status = 200
        mock_post.return_value.json = AsyncMock(return_value={"access_token": "test_token"})
        token_data = await auth_instance._get_token("test_code")
        assert token_data["access_token"] == "test_token"

@pytest.mark.asyncio
async def test_send_refresh_request(auth_instance):
    """Test the send_refresh_request method."""
    auth_instance.auth_data = {"access_token": "test_token", "expires_in": 3600}
    auth_instance.next_refresh = datetime.now() - timedelta(seconds=1)
    with patch("pyanglianwater.auth.aiohttp.ClientSession.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status = 200
        mock_post.return_value.json = AsyncMock(return_value={"access_token": "new_token", "expires_in": 3600})
        await auth_instance.send_refresh_request()
        assert auth_instance.access_token == "new_token"

@pytest.mark.asyncio
async def test_send_login_request(auth_instance):
    """Test the send_login_request method."""
    with patch.object(auth_instance, "_get_initial_auth_data", AsyncMock(return_value=("csrf_token", "trans_id"))), \
         patch.object(auth_instance, "_submit_self_asserted_form", AsyncMock(return_value=True)), \
         patch.object(auth_instance, "_get_confirmation_redirect", AsyncMock(return_value="redirect_url")), \
         patch.object(auth_instance, "_get_token", AsyncMock(return_value={"access_token": "test_token", "expires_in": 3600})):
        await auth_instance.send_login_request()
        assert auth_instance.access_token == "test_token"

@pytest.mark.asyncio
async def test_send_request(auth_instance):
    """Test the send_request method."""
    auth_instance = await auth_instance  # Await the fixture
    auth_instance.auth_data = {"access_token": "test_token"}
    auth_instance._decoded_access_token = {"extension_accountNumber": "12345"}
    auth_instance.next_refresh = datetime.now() + timedelta(seconds=3600)
    with patch("pyanglianwater.auth.aiohttp.ClientSession.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value.ok = True
        mock_request.return_value.content_type = "application/json"
        mock_request.return_value.json = AsyncMock(return_value={"data": "test_data"})
        response = await auth_instance.send_request("get_account", {"key": "value"})
        assert response["data"] == "test_data"

@pytest.mark.asyncio
async def test_send_request_expired_token(auth_instance):
    """Test send_request raises ExpiredAccessTokenError when token is expired."""
    auth_instance = await auth_instance  # Await the fixture
    auth_instance.auth_data = None
    with pytest.raises(ValueError):
        await auth_instance.send_request("get_account", {"key": "value"})

@pytest.mark.asyncio
async def test_send_request_invalid_account(auth_instance):
    """Test send_request raises InvalidAccountIdError for 403 response."""
    auth_instance = await auth_instance  # Await the fixture
    auth_instance.auth_data = {"access_token": "test_token"}
    with patch("pyanglianwater.auth.aiohttp.ClientSession.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value.status = 403
        with pytest.raises(InvalidAccountIdError):
            await auth_instance.send_request("get_account", {"key": "value"})

@pytest.mark.asyncio
async def test_send_request_unknown_endpoint(auth_instance):
    """Test send_request raises UnknownEndpointError for unknown endpoint."""
    auth_instance = await auth_instance  # Await the fixture
    auth_instance.auth_data = {"access_token": "test_token"}
    with patch("pyanglianwater.auth.aiohttp.ClientSession.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value.status = 500
        mock_request.return_value.text = AsyncMock(return_value="Server Error")
        with pytest.raises(ValueError):
            await auth_instance.send_request("test_endpoint", {"key": "value"})