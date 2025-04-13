import pytest
from unittest.mock import AsyncMock, MagicMock
from pyanglianwater.api import API
from pyanglianwater.auth import BaseAuth

@pytest.fixture
def mock_auth():
    """Fixture for a mocked BaseAuth object."""
    mock = MagicMock(spec=BaseAuth)
    mock.account_number = "123456789"
    mock.primary_bp_number = "987654321"
    mock.username = "test_user"
    mock.next_refresh = "2023-12-31T23:59:59Z"
    mock.send_request = AsyncMock(return_value={"status": "success"})
    mock.send_refresh_request = AsyncMock(return_value={"status": "token_refreshed"})
    mock.send_login_request = AsyncMock(return_value={"status": "logged_in"})
    return mock

@pytest.fixture
def api(mock_auth):
    """Fixture for the API object."""
    return API(auth_obj=mock_auth)

@pytest.mark.asyncio
async def test_send_request(api, mock_auth):
    """Test the send_request method."""
    endpoint = "/test-endpoint"
    body = {"key": "value"}
    response = await api.send_request(endpoint=endpoint, body=body)
    mock_auth.send_request.assert_awaited_once_with(endpoint=endpoint, body=body)
    assert response == {"status": "success"}

@pytest.mark.asyncio
async def test_token_refresh(api, mock_auth):
    """Test the token_refresh method."""
    response = await api.token_refresh()
    mock_auth.send_refresh_request.assert_awaited_once()
    assert response == {"status": "token_refreshed"}

@pytest.mark.asyncio
async def test_login(api, mock_auth):
    """Test the login method."""
    response = await api.login()
    mock_auth.send_login_request.assert_awaited_once()
    assert response == {"status": "logged_in"}

def test_account_number(api):
    """Test the account_number property."""
    assert api.account_number == "123456789"

def test_primary_bp_number(api):
    """Test the primary_bp_number property."""
    assert api.primary_bp_number == "987654321"

def test_username(api):
    """Test the username property."""
    assert api.username == "test_user"

def test_to_dict(api):
    """Test the to_dict method."""
    expected_dict = {
        "account_number": "123456789",
        "username": "test_user",
        "next_refresh": "2023-12-31T23:59:59Z"
    }
    assert api.to_dict() == expected_dict

def test_iter(api):
    """Test the __iter__ method."""
    api_dict = dict(api)
    expected_dict = {
        "account_number": "123456789",
        "username": "test_user",
        "next_refresh": "2023-12-31T23:59:59Z"
    }
    assert api_dict == expected_dict