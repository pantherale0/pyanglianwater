import json
import pytest
import aiohttp
from pathlib import Path
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from pyanglianwater.auth import MSOB2CAuth

from pyanglianwater.exceptions import (
    InvalidAccountIdError,
    InvalidGrantError,
    InvalidRequestError,
    InvalidClientError,
    UnauthorizedClientError,
    UnsupportedGrantTypeError,
    InvalidScopeError,
    AccessDeniedError,
    InteractionRequiredError,
    LoginRequiredError,
    ConsentRequiredError,
    TemporarilyUnavailableError,
    TokenRequestError,
    ExpiredAccessTokenError,
    UnknownEndpointError,
)


@pytest.fixture
async def auth_instance():
    """Fixture to create an instance of MSOB2CAuth."""
    async with aiohttp.ClientSession() as session:
        return MSOB2CAuth(username="testuser", password="testpassword", session=session)


@pytest.fixture
def refresh_invalid_grant_response_text():
    """Sample refresh-token invalid_grant API payload as raw response text."""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "refresh_invalid_grant_response.json"
    )
    return fixture_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_initial_auth_data(auth_instance):
    """Test the _get_initial_auth_data method."""
    with patch(
        "pyanglianwater.auth.aiohttp.ClientSession.get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value.ok = True
        mock_get.return_value.status = 302
        mock_get.return_value.headers = {"Location": "https://example.com"}
        location = await auth_instance._get_initial_auth_data()
        assert location == "https://example.com"


@pytest.mark.asyncio
async def test_submit_self_asserted_form(auth_instance):
    """Test the _submit_self_asserted_form method."""
    with patch(
        "pyanglianwater.auth.aiohttp.ClientSession.post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value.status = 200
        mock_post.return_value.json = AsyncMock(return_value={"status": 200})
        response = await auth_instance._submit_self_asserted_form("test_trans_id")
        assert response is not None


@pytest.mark.asyncio
async def test_get_confirmation_redirect(auth_instance):
    """Test the _get_confirmation_redirect method."""
    with patch(
        "pyanglianwater.auth.aiohttp.ClientSession.get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value.status = 302
        mock_get.return_value.headers = {"Location": "https://example.com"}
        location = await auth_instance._get_confirmation_redirect()
        assert location == "https://example.com"


@pytest.mark.asyncio
async def test_get_token(auth_instance):
    """Test the _get_token method."""
    with patch(
        "pyanglianwater.auth.aiohttp.ClientSession.post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value.status = 200
        mock_post.return_value.json = AsyncMock(
            return_value={"access_token": "test_token"}
        )
        token_data = await auth_instance._get_token("test_code")
        assert token_data["access_token"] == "test_token"


@pytest.mark.asyncio
async def test_send_refresh_request(auth_instance):
    """Test the send_refresh_request method."""
    auth_instance.auth_data = {"access_token": "test_token", "expires_in": 3600}
    auth_instance.next_refresh = datetime.now() - timedelta(seconds=1)
    with patch(
        "pyanglianwater.auth.aiohttp.ClientSession.post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.return_value.status = 200
        mock_post.return_value.json = AsyncMock(
            return_value={"access_token": "new_token", "expires_in": 3600}
        )
        await auth_instance.send_refresh_request()
        assert auth_instance.access_token == "new_token"


@pytest.mark.asyncio
async def test_send_login_request(auth_instance):
    """Test the send_login_request method."""
    with (
        patch.object(
            auth_instance,
            "_get_initial_auth_data",
            AsyncMock(return_value=("csrf_token", "trans_id")),
        ),
        patch.object(
            auth_instance, "_submit_self_asserted_form", AsyncMock(return_value=True)
        ),
        patch.object(
            auth_instance,
            "_get_confirmation_redirect",
            AsyncMock(
                return_value="uk.co.anglianwater.myaccount://?code=test_code&state=test_state"
            ),
        ),
        patch.object(
            auth_instance,
            "_get_token",
            AsyncMock(return_value={"access_token": "test_token", "expires_in": 3600}),
        ),
    ):
        await auth_instance.send_login_request()
        assert auth_instance.access_token == "test_token"


@pytest.mark.asyncio
async def test_send_request(auth_instance):
    """Test the send_request method."""
    auth_instance.auth_data = {"access_token": "test_token"}
    auth_instance.next_refresh = datetime.now() + timedelta(seconds=3600)
    with patch.object(auth_instance, "send_refresh_request", AsyncMock()):
        mock_response = AsyncMock()
        mock_response.ok = True
        mock_response.content_type = "application/json"
        mock_response.json = AsyncMock(return_value={"data": "test_data"})

        with patch.object(auth_instance._auth_session, "request") as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            mock_request.return_value.__aexit__.return_value = AsyncMock()

            response = await auth_instance.send_request(
                "GET", "https://example.com/api", None, {}
            )
            assert response["data"] == "test_data"


@pytest.mark.asyncio
async def test_send_request_expired_token(auth_instance):
    """Test send_request raises ExpiredAccessTokenError when token is expired."""
    auth_instance.auth_data = None
    with patch.object(auth_instance, "send_refresh_request", AsyncMock()):
        with pytest.raises(ExpiredAccessTokenError):
            await auth_instance.send_request("GET", "https://example.com/api", None, {})


@pytest.mark.asyncio
async def test_send_request_invalid_account(auth_instance):
    """Test send_request raises InvalidAccountIdError for 403 response."""
    auth_instance.auth_data = {"access_token": "test_token"}
    auth_instance.next_refresh = datetime.now() + timedelta(seconds=3600)
    with patch.object(auth_instance, "send_refresh_request", AsyncMock()):
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.ok = False

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = None

        with patch.object(auth_instance._auth_session, "request", return_value=mock_cm):
            with pytest.raises(InvalidAccountIdError):
                await auth_instance.send_request(
                    "GET", "https://example.com/api", None, {}
                )


@pytest.mark.asyncio
async def test_send_request_unknown_endpoint(auth_instance):
    """Test send_request raises UnknownEndpointError for unknown endpoint."""
    auth_instance.auth_data = {"access_token": "test_token"}
    auth_instance.next_refresh = datetime.now() + timedelta(seconds=3600)
    with patch.object(auth_instance, "send_refresh_request", AsyncMock()):
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.ok = False
        mock_response.text = AsyncMock(return_value="Server Error")

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = None

        with patch.object(auth_instance._auth_session, "request", return_value=mock_cm):
            with pytest.raises(UnknownEndpointError):
                await auth_instance.send_request(
                    "GET", "https://example.com/api", None, {}
                )


@pytest.mark.parametrize(
    "error_code,expected_exception",
    [
        ("invalid_grant", InvalidGrantError),
        ("invalid_request", InvalidRequestError),
        ("invalid_client", InvalidClientError),
        ("unauthorized_client", UnauthorizedClientError),
        ("unsupported_grant_type", UnsupportedGrantTypeError),
        ("invalid_scope", InvalidScopeError),
        ("access_denied", AccessDeniedError),
        ("interaction_required", InteractionRequiredError),
        ("login_required", LoginRequiredError),
        ("consent_required", ConsentRequiredError),
        ("temporarily_unavailable", TemporarilyUnavailableError),
    ],
)
def test_raise_mapped_token_error_oauth_codes(error_code, expected_exception):
    """Mapped OAuth errors should raise their specific custom exception."""
    auth = MSOB2CAuth(username="testuser", password="testpassword", session=AsyncMock())
    response_text = json.dumps(
        {"error": error_code, "error_description": f"test-message-for-{error_code}"}
    )
    with pytest.raises(expected_exception):
        auth._raise_mapped_token_error(status=400, response_text=response_text)


@pytest.mark.parametrize(
    "error_message,error_codes,expected_exception",
    [
        ("AADSTS700082: Refresh token expired", None, InvalidGrantError),
        ("AADSTS65001: Consent required", None, ConsentRequiredError),
        ("AADSTS50076: MFA required", None, InteractionRequiredError),
        ("AADSTS50079: MFA registration required", None, InteractionRequiredError),
        ("AADB2C90091: User cancelled the flow", None, AccessDeniedError),
        ("AADB2C90118: Password reset requested", None, InteractionRequiredError),
        ("Generic message", [50076], InteractionRequiredError),
    ],
)
def test_raise_mapped_token_error_entra_hints(
    error_message, error_codes, expected_exception
):
    """Known Entra/B2C hints should map to specific custom exceptions."""
    auth = MSOB2CAuth(username="testuser", password="testpassword", session=AsyncMock())
    response_text = json.dumps(
        {
            "error": "unknown_error",
            "error_description": error_message,
            "error_codes": error_codes or [],
        }
    )
    with pytest.raises(expected_exception):
        auth._raise_mapped_token_error(status=400, response_text=response_text)


@pytest.mark.parametrize("status", [400, 401, 403, 500, 503])
def test_raise_mapped_token_error_falls_back_to_token_request_error(status):
    """Unknown token failures at any non-200 status should fall back to TokenRequestError."""
    auth = MSOB2CAuth(username="testuser", password="testpassword", session=AsyncMock())
    with pytest.raises(TokenRequestError):
        auth._raise_mapped_token_error(
            status=status,
            response_text="unexpected token endpoint failure",
        )


def test_raise_mapped_token_error_real_invalid_grant_refresh_fixture(
    refresh_invalid_grant_response_text,
):
    """Real-world invalid_grant refresh payload should map to InvalidGrantError."""
    auth = MSOB2CAuth(username="testuser", password="testpassword", session=AsyncMock())
    with pytest.raises(InvalidGrantError) as exc:
        auth._raise_mapped_token_error(
            status=400,
            response_text=refresh_invalid_grant_response_text,
        )
    assert "AADB2C90080" in str(exc.value)
