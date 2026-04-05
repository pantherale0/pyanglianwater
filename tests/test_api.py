"""Tests for the API module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyanglianwater.api import API
from pyanglianwater.auth import MSOB2CAuth


@pytest.fixture
def mock_auth():
    """Fixture for a mocked MSOB2CAuth object."""
    mock = MagicMock(spec=MSOB2CAuth)
    mock.username = "test_user"
    mock.business_partner_number = "987654321"
    mock.next_refresh = "2023-12-31T23:59:59Z"
    mock.authenticated_headers = {"Authorization": "Bearer test_token"}
    mock.send_request = AsyncMock(return_value={"status": "success"})
    mock.send_refresh_request = AsyncMock(return_value={"status": "token_refreshed"})
    mock.send_login_request = AsyncMock(return_value={"status": "logged_in"})
    return mock


@pytest.fixture
def api(mock_auth):  # pylint: disable=redefined-outer-name
    """Fixture for the API object."""
    return API(auth_obj=mock_auth)


@pytest.mark.asyncio
async def test_send_request(api, mock_auth):  # pylint: disable=redefined-outer-name
    """Test the send_request method."""
    endpoint = "get_associated_accounts"
    body = None
    account_number = "12345"
    response = await api.send_request(endpoint=endpoint, body=body, account_number=account_number)
    mock_auth.send_request.assert_awaited_once()
    assert response == {"status": "success"}


@pytest.mark.asyncio
async def test_token_refresh(api, mock_auth):  # pylint: disable=redefined-outer-name
    """Test the token_refresh method."""
    response = await api.token_refresh()
    mock_auth.send_refresh_request.assert_awaited_once()
    assert response == {"status": "token_refreshed"}


@pytest.mark.asyncio
async def test_login(api, mock_auth):  # pylint: disable=redefined-outer-name
    """Test the login method."""
    response = await api.login()
    mock_auth.send_login_request.assert_awaited_once()
    assert response == {"status": "logged_in"}


def test_username(api):  # pylint: disable=redefined-outer-name
    """Test the username property."""
    assert api.username == "test_user"


def test_to_dict(api):  # pylint: disable=redefined-outer-name
    """Test the to_dict method."""
    result = api.to_dict()
    assert "username" in result
    assert result["username"] == "test_user"
    assert "next_refresh" in result


def test_iter(api):  # pylint: disable=redefined-outer-name
    """Test the __iter__ method."""
    api_dict = dict(api)
    assert "username" in api_dict
    assert api_dict["username"] == "test_user"
    assert "next_refresh" in api_dict
