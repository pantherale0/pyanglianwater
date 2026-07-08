"""Authentication handlers."""

import secrets
import urllib.parse
import re
import logging
import json

from datetime import datetime, timedelta

import aiohttp

from .const import (
    AUTH_MSO_STEP_1_URL,
    AUTH_MSO_SELF_ASSERTED_URL,
    AUTH_MSO_GET_TOKEN_URL,
    AUTH_AW_BASE,
    AUTH_MSO_CONFIRM_URL,
    AUTH_MSO_CONFIRM_URL_NO_REMEMBER,
    AUTH_MSO_SELF_ASSERTED_CONFIRM_URL,
    AUTH_MSO_CLIENT_ID,
    AUTH_MSO_REDIR_URI,
    AW_APP_USER_AGENT,
)
from .exceptions import (
    ExpiredAccessTokenError,
    UnknownEndpointError,
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
    SelfAssertedError,
    MFARequiredError,
    ConfirmationRedirectError,
    TokenRequestError,
)
from .utils import (
    random_string,
    build_code_challenge,
    decode_oauth_redirect,
    decode_jwt,
)

_LOGGER = logging.getLogger(__name__)


OAUTH_ERROR_EXCEPTION_MAP = {
    "invalid_grant": InvalidGrantError,
    "invalid_request": InvalidRequestError,
    "invalid_client": InvalidClientError,
    "unauthorized_client": UnauthorizedClientError,
    "unsupported_grant_type": UnsupportedGrantTypeError,
    "invalid_scope": InvalidScopeError,
    "access_denied": AccessDeniedError,
    "interaction_required": InteractionRequiredError,
    "login_required": LoginRequiredError,
    "consent_required": ConsentRequiredError,
    "temporarily_unavailable": TemporarilyUnavailableError,
}

# Frequently seen Entra/B2C sub-codes surfaced inside `error_description`
ENTRA_ERROR_HINTS = {
    "AADSTS700082": InvalidGrantError,  # Refresh token expired due to inactivity
    "AADSTS65001": ConsentRequiredError,  # Consent required
    "AADSTS50076": InteractionRequiredError,  # MFA required
    "AADSTS50079": InteractionRequiredError,  # MFA registration required
    "AADB2C90091": AccessDeniedError,  # User cancelled flow
    "AADB2C90118": InteractionRequiredError,  # Password reset requested
    "AADB2C90080": InvalidGrantError,  # Refresh token expired due to inactivity
}


class MSOB2CAuth:
    """Represent an instance of MSO Auth."""

    _auth_session: aiohttp.ClientSession | None = None
    username: str = None
    _password: str = None
    next_refresh: datetime = None
    auth_data: dict = None
    _pkce_verifier = random_string(43, 128)
    _pkce_challenge = None
    _state = secrets.token_urlsafe(32)
    _csrf_token: str = ""
    _cookie_cache: dict = {}
    _trans_id: str | None = None
    _mfa_readonly_email: str | None = None
    _mfa_pending: bool = False

    def __init__(self, username, password, session=None, refresh_token=None):
        if session:
            self._auth_session = session
        else:
            self._auth_session = aiohttp.ClientSession()
        self.username = username
        self._password = password
        self._refresh_token = refresh_token

    @property
    def business_partner_number(self) -> str | None:
        """Return business partner number."""
        if self.auth_data is None:
            return None
        return self.auth_data.get("extension_business_partner_number", "")

    @property
    def access_token(self) -> str:
        """Return the access token."""
        if self.auth_data is None:
            return None
        return self.auth_data.get("access_token")

    @property
    def refresh_token(self) -> str:
        """Return the access token."""
        if self._refresh_token is not None:
            return self._refresh_token
        if self.auth_data is None:
            return None
        return self.auth_data.get("refresh_token")

    @property
    def authenticated_headers(self) -> dict:
        """Return authenticated headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Ocp-Apim-Subscription-Key": "adbc43b29a87404cbc297fe6d7a3d10e",
            "Accept": "application/json",
            "User-Agent": AW_APP_USER_AGENT,
        }

    async def _get_initial_auth_data(self):
        """Retrieves initial authentication data (CSRF token, transId)."""
        _LOGGER.debug("B2C Auth: Getting initial auth data")
        self._state = secrets.token_urlsafe(32)
        self._pkce_challenge = build_code_challenge(self._pkce_verifier)
        auth_response = await self._auth_session.get(
            AUTH_MSO_STEP_1_URL.format(
                CODE_CHALLENGE=self._pkce_challenge,
                EMAIL=self.username,
                STATE=self._state,
            ),
            allow_redirects=False,
        )

        if not auth_response.ok:
            data = await auth_response.text()
            _LOGGER.error(
                "B2C Auth: Initial Authorization URL request failed %s: %s",
                auth_response.status,
                data,
            )
            return None

        if auth_response.status == 302:
            location = auth_response.headers.get("Location")
            if not location:
                _LOGGER.error("B2C Auth: Location header not found")
                return None
            return location

        html = await auth_response.text()
        match = re.search(r"var SETTINGS = {([^;]+)};", html)
        if not match:
            _LOGGER.error("B2C Auth: SETTINGS object not found in HTML")
            return None

        settings_json_str = match.group(1)
        csrf_match = re.search(r'"csrf":\s*"([^"]+)"', settings_json_str)
        trans_id_match = re.search(r'"transId":\s*"([^"]+)"', settings_json_str)

        if not csrf_match or not trans_id_match:
            _LOGGER.error("B2C Auth: CSRF or Transaction ID not found in SETTINGS")
            return None

        _csrf_token = csrf_match.group(1)
        trans_id = trans_id_match.group(1)

        _LOGGER.debug("Got CSRF %s and Transaction ID %s", _csrf_token, trans_id)

        return _csrf_token, trans_id

    async def _submit_self_asserted_form(self, trans_id):
        """Submits the SelfAsserted form."""
        _LOGGER.debug("B2C Auth: Submitting self-asserted form")
        data = {
            "request_type": "RESPONSE",
            "email": self.username,
            "password": self._password,
        }
        asserted_login_response = await self._auth_session.post(
            AUTH_MSO_SELF_ASSERTED_URL.format(STATE=trans_id),
            headers={
                "X-CSRF-TOKEN": self._csrf_token,
                "Referer": AUTH_MSO_STEP_1_URL.format(
                    CODE_CHALLENGE=self._pkce_challenge,
                    EMAIL=self.username,
                    STATE=self._state,
                ),
                "Origin": AUTH_AW_BASE,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": AW_APP_USER_AGENT,
            },
            data=data,
        )
        data = await asserted_login_response.json(content_type="text/json")
        status = int(data.get("status"))
        if asserted_login_response.status != 200 or status != 200:
            _LOGGER.error(
                "B2C Auth: SelfAsserted request failed %s: %s",
                asserted_login_response.status,
                data,
            )
            if status == 400:
                raise SelfAssertedError(
                    f"{data.get('errorCode', 'Unknown')} {data.get('message', 'Unknown')}"
                )
            return None

        return asserted_login_response

    def _is_mfa_challenge_page(self, html: str) -> bool:
        """Heuristically determine whether the confirmed page asks for MFA."""
        # In the observed HTML, MFA is signalled via `2fa_login_challenge.html`
        # and the presence of a `verificationCode` input definition.
        if re.search(r"2fa[_-]login[_-]challenge\.html", html, flags=re.I):
            return True
        if re.search(r"\b2fa\b", html, flags=re.I) and re.search(
            r'"ID"\s*:\s*"verificationCode"', html, flags=re.I
        ):
            return True
        return False

    def _extract_readonly_email_from_mfa_html(self, html: str) -> str | None:
        """Extract readonlyEmail from the MFA page HTML."""
        # Observed in HTML as:
        # { ... "ID":"readonlyEmail", "PRE":"jordan@hrvy.uk", ...}
        match = re.search(
            r'"ID"\s*:\s*"readonlyEmail".{0,800}?"PRE"\s*:\s*"([^"]+?)"',
            html,
            flags=re.I | re.S,
        )
        if match:
            return match.group(1)
        return None

    def _extract_mfa_csrf_from_mfa_html(self, html: str) -> str | None:
        """Extract SETTINGS.csrf from MFA challenge HTML."""
        # Observed in the MFA challenge HTML as:
        # var SETTINGS = {...,"csrf":"<value>",...};
        # Use a bounded match first to avoid scanning the entire HTML document.
        settings_match = re.search(
            r"var\s+SETTINGS\s*=\s*\{([^;]+)\};",
            html,
            flags=re.I | re.S,
        )
        if not settings_match:
            return None

        csrf_match = re.search(
            r'"csrf"\s*:\s*"([^"]+?)"',
            settings_match.group(1),
            flags=re.I,
        )
        if csrf_match:
            return csrf_match.group(1)
        return None

    async def _submit_mfa_self_asserted_form(
        self, trans_id: str, verification_code: str
    ):
        """Submits the MFA SelfAsserted form (second POST after the challenge)."""
        if not self._mfa_readonly_email:
            raise ValueError("MFA readonlyEmail not available; resume after MFARequiredError")

        _LOGGER.debug("B2C Auth: Submitting MFA self-asserted form")
        data = {
            "request_type": "RESPONSE",
            "readonlyEmail": self._mfa_readonly_email,
            "verificationCode": verification_code,
        }

        asserted_login_response = await self._auth_session.post(
            AUTH_MSO_SELF_ASSERTED_URL.format(STATE=trans_id),
            headers={
                "X-CSRF-TOKEN": self._csrf_token,
                # The confirmed endpoint is what surfaces the MFA challenge,
                # so we use it as referer for the follow-up verification POST.
                "Referer": AUTH_MSO_CONFIRM_URL_NO_REMEMBER.format(
                    CSRF=self._csrf_token,
                    STATE=self._state,
                ),
                "Origin": AUTH_AW_BASE,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": AW_APP_USER_AGENT,
            },
            data=data,
        )

        try:
            data = await asserted_login_response.json(content_type="text/json")
            if not isinstance(data, dict) or "status" not in data:
                raise ValueError("Missing status in MFA response")
            status = int(data["status"])
        except (
            aiohttp.ContentTypeError,
            json.JSONDecodeError,
            ValueError,
            TypeError,
        ) as e:
            text = await asserted_login_response.text()
            _LOGGER.error(
                "B2C Auth: MFA SelfAsserted returned invalid response (%s): %s",
                asserted_login_response.status,
                text,
            )
            raise SelfAssertedError(
                f"Unexpected MFA response ({asserted_login_response.status})"
            ) from e
        if asserted_login_response.status != 200 or status != 200:
            _LOGGER.error(
                "B2C Auth: MFA SelfAsserted request failed %s: %s",
                asserted_login_response.status,
                data,
            )
            raise SelfAssertedError(
                f"{data.get('errorCode', 'Unknown')} {data.get('message', 'Unknown')}"
            )

        return asserted_login_response

    async def _get_confirmation_redirect(self):
        """Gets the confirmation redirect URL."""
        _LOGGER.debug("B2C Auth: Getting confirmation redirect URL")
        confirm_login_response = await self._auth_session.get(
            AUTH_MSO_CONFIRM_URL.format(CSRF=self._csrf_token, STATE=self._state),
            allow_redirects=False,
        )

        if confirm_login_response.status == 200:
            text = await confirm_login_response.text()

            terms_of_use_match = re.search(
                r'"ID"\s*:\s*"extension_termsOfUseConsentChoice"', text
            )
            is_req_match = re.search(r'"IS_REQ"\s*:\s*true', text)
            if terms_of_use_match and is_req_match:
                raise ConsentRequiredError("Terms of use not accepted")

            if self._is_mfa_challenge_page(text):
                readonly_email = self._extract_readonly_email_from_mfa_html(text)
                # MFA uses a *different* CSRF token for the verification POST and the
                # subsequent SelfAsserted confirmation redirect.
                mfa_csrf = self._extract_mfa_csrf_from_mfa_html(text)
                if mfa_csrf:
                    self._csrf_token = mfa_csrf
                self._mfa_readonly_email = readonly_email
                self._mfa_pending = True
                raise MFARequiredError(readonly_email=readonly_email)
            # Not a redirect and not the MFA challenge page: treat as failure
            # so callers don't silently proceed without an access token.
            raise ConfirmationRedirectError(
                "Confirmed endpoint returned a 200 response but no redirect URL was provided"
            )

        if confirm_login_response.status != 302:
            text = await confirm_login_response.text()
            _LOGGER.error(
                "B2C Auth: Confirm request failed %s: %s",
                confirm_login_response.status,
                text,
            )
            raise ConfirmationRedirectError(
                f"Confirmed endpoint returned status {confirm_login_response.status}"
            )

        location = confirm_login_response.headers.get("Location")
        if not location:
            _LOGGER.error("B2C Auth: Location header not found")
            raise ConfirmationRedirectError("Location header not found on confirmed redirect")

        return location

    async def _get_self_asserted_confirmation_redirect(self) -> str:
        """After MFA verification, confirmed redirect is served by SelfAsserted."""
        _LOGGER.debug("B2C Auth: Getting self-asserted confirmation redirect URL")
        confirm_login_response = await self._auth_session.get(
            AUTH_MSO_SELF_ASSERTED_CONFIRM_URL.format(
                CSRF=self._csrf_token, STATE=self._state
            ),
            allow_redirects=False,
        )

        if confirm_login_response.status != 302:
            text = await confirm_login_response.text()
            _LOGGER.error(
                "B2C Auth: SelfAsserted confirm request failed %s: %s",
                confirm_login_response.status,
                text,
            )
            raise ConfirmationRedirectError(
                f"SelfAsserted confirm returned {confirm_login_response.status}"
            )

        location = confirm_login_response.headers.get("Location")
        if not location:
            raise ConfirmationRedirectError(
                "Location header not found on SelfAsserted confirmation"
            )

        return location

    async def _get_token(self, code):
        """Requests the access token."""
        _LOGGER.debug("B2C Auth: Getting access token from authorization code")
        token_request_response = await self._auth_session.post(
            AUTH_MSO_GET_TOKEN_URL,
            data=urllib.parse.urlencode(
                {
                    "grant_type": "authorization_code",
                    "client_id": AUTH_MSO_CLIENT_ID,
                    "redirect_uri": AUTH_MSO_REDIR_URI,
                    "code": code,
                    "code_verifier": self._pkce_verifier,
                }
            ),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": AW_APP_USER_AGENT,
            },
        )

        if token_request_response.status != 200:
            text = await token_request_response.text()
            self._raise_mapped_token_error(
                status=token_request_response.status,
                response_text=text,
            )

        try:
            token_data = await token_request_response.json()
            return token_data
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            _LOGGER.error("B2C Auth: Error processing token response: %s", e)
            return None

    async def send_refresh_request(self):
        """Send a request to refresh the access token."""
        _LOGGER.debug("B2C Auth: Refreshing access token")
        if self.access_token is None and self.refresh_token is None:
            raise ValueError("Not logged in.")
        if self.next_refresh is not None:
            if self.next_refresh > datetime.now():
                _LOGGER.debug("B2C Auth: Access token not yet expired")
                return
        token_request_response = await self._auth_session.post(
            AUTH_MSO_GET_TOKEN_URL,
            data=urllib.parse.urlencode(
                {
                    "grant_type": "refresh_token",
                    "client_id": AUTH_MSO_CLIENT_ID,
                    "refresh_token": self.refresh_token,
                }
            ),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": AW_APP_USER_AGENT,
            },
        )

        if token_request_response.status != 200:
            text = await token_request_response.text()
            self._raise_mapped_token_error(
                status=token_request_response.status,
                response_text=text,
            )

        try:
            token_data = await token_request_response.json()
            self.auth_data = token_data
            self.next_refresh = datetime.now() + timedelta(
                seconds=token_data["expires_in"]
            )
            self.auth_data = {**self.auth_data, **decode_jwt(self.access_token)}
            _LOGGER.debug(
                "B2C Auth: Access token refreshed successfully, new expiration time: %s",
                self.next_refresh,
            )
        except (aiohttp.ClientError, json.JSONDecodeError) as e:
            _LOGGER.error("B2C Auth: Error processing refresh response: %s", e)
            raise TokenRequestError(f"Error processing refresh response: {e}") from e

    def _raise_mapped_token_error(
        self,
        status: int,
        response_text: str,
    ) -> None:
        """Raise a mapped exception for known OAuth/Entra/B2C token errors."""
        try:
            error_data = json.loads(response_text)
            if not isinstance(error_data, dict):
                error_data = {}
            error_code = error_data.get("error", "Unknown")
            error_message = error_data.get("error_description") or response_text
            error_codes = error_data.get("error_codes")
        except json.JSONDecodeError:
            error_code = "Unknown"
            error_message = response_text
            error_codes = None

        normalized_error_code = str(error_code or "").lower()
        exception_class = OAUTH_ERROR_EXCEPTION_MAP.get(normalized_error_code)
        if exception_class is not None:
            _LOGGER.error(
                "B2C Auth: OAuth token error (%s) during token request: %s",
                normalized_error_code,
                error_message,
            )
            raise exception_class(error_message)

        normalized_error_codes = {str(code) for code in (error_codes or [])}
        for entra_code, mapped_exception in ENTRA_ERROR_HINTS.items():
            entra_numeric = entra_code.removeprefix("AADSTS").removeprefix("AADB2C")
            if (
                entra_code in error_message
                or entra_code in normalized_error_codes
                or entra_numeric in normalized_error_codes
            ):
                _LOGGER.error(
                    "B2C Auth: Entra/B2C token error (%s) during token request: %s",
                    entra_code,
                    error_message,
                )
                raise mapped_exception(error_message)

        if status != 200:
            _LOGGER.error(
                "B2C Auth: Token request failed %s: %s",
                status,
                response_text,
            )
            raise TokenRequestError(error_message)

    async def send_login_request(self):
        """Send a request to MSO for Auth."""
        # Clear any previous pending MFA state from earlier attempts.
        self._mfa_pending = False
        self._mfa_readonly_email = None
        self._trans_id = None

        if self._refresh_token is not None:
            _LOGGER.debug("B2C Auth: Using refresh token for authentication")
            # Attempt to use refresh token first
            try:
                await self.send_refresh_request()
                return
            except InvalidGrantError:
                pass # Refresh token invalid/expired, fall back to full login flow
        auth_data = await self._get_initial_auth_data()
        if auth_data is None:
            return
        if isinstance(auth_data, tuple):
            self._csrf_token, trans_id = auth_data
            self._trans_id = trans_id
            asserted_response = await self._submit_self_asserted_form(trans_id)
            if asserted_response is None:
                return
            redirect_location = await self._get_confirmation_redirect()
            if redirect_location is None:
                return
        elif "uk.co.anglianwater.myaccount://" in auth_data:
            redirect_location = auth_data
        _, code = decode_oauth_redirect(redirect_location)
        if not code:
            _LOGGER.error("B2C Auth: Code not found")
            return

        token_response = await self._get_token(code)
        if token_response is None:
            _LOGGER.error("B2C Auth: Token request failed")
            return

        self.auth_data = token_response
        try:
            expires_in = int(token_response.get("expires_in", 3600))
        except (ValueError, TypeError):
            expires_in = 3600
        self.next_refresh = datetime.now() + timedelta(seconds=expires_in)
        self._refresh_token = token_response.get("refresh_token")
        access_token = self.access_token
        if access_token:
            self.auth_data = {**self.auth_data, **decode_jwt(access_token)}
        _LOGGER.debug(
            "B2C Auth: Access token obtained successfully, new expiration time: %s",
            self.next_refresh,
        )

    async def send_mfa_request(self, verification_code: str) -> None:
        """Resume the MFA flow by submitting the verification code."""
        if not self._mfa_pending or not self._trans_id:
            raise ValueError("MFA not pending; call send_login_request() first")
        if not self._csrf_token:
            raise ValueError("Missing CSRF token; call send_login_request() first")

        # Submit the MFA code
        try:
            await self._submit_mfa_self_asserted_form(
                self._trans_id, verification_code
            )
        except SelfAssertedError as exc:
            # Browser stays on the MFA step for invalid/expired codes.
            # Re-signal the MFA requirement so callers can prompt again
            # without restarting the login flow.
            raise MFARequiredError(
                readonly_email=self._mfa_readonly_email
            ) from exc

        # Confirmation should now complete with a 302 redirect containing the auth code.
        redirect_location = await self._get_self_asserted_confirmation_redirect()

        _, code = decode_oauth_redirect(redirect_location)
        if not code:
            _LOGGER.error("B2C Auth: Code not found after MFA")
            raise ConfirmationRedirectError("Auth code not found after MFA")

        token_response = await self._get_token(code)
        if token_response is None:
            _LOGGER.error("B2C Auth: Token request failed after MFA")
            raise TokenRequestError("Token request failed after MFA")

        self.auth_data = token_response
        try:
            expires_in = int(token_response.get("expires_in", 3600))
        except (ValueError, TypeError):
            expires_in = 3600
        self.next_refresh = datetime.now() + timedelta(seconds=expires_in)
        self._refresh_token = token_response.get("refresh_token")
        access_token = self.access_token
        if access_token:
            self.auth_data = {**self.auth_data, **decode_jwt(access_token)}

        # MFA is satisfied; clear pending state.
        self._mfa_pending = False
        self._mfa_readonly_email = None
        self._trans_id = None

    async def send_request(
        self, method: str, url: str, body: dict | None, headers: dict
    ) -> dict:
        """Send a request to the API, and return the JSON response."""
        await self.send_refresh_request()
        if self.access_token is None:
            _LOGGER.debug("Access token unavailable, not logged in.")
            raise ExpiredAccessTokenError()
        async with self._auth_session.request(
            method=method, url=url, headers=headers, json=body
        ) as _response:
            _LOGGER.debug(
                "Request to %s returned with status %s", url, _response.status
            )
            if _response.ok and _response.content_type == "application/json":
                return await _response.json()
            if _response.status == 401:
                raise ExpiredAccessTokenError()
            if _response.status == 403:
                raise InvalidAccountIdError()
            raise UnknownEndpointError(_response.status, await _response.text())
