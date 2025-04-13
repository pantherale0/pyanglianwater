"""Anglian Water consts."""

AW_TARIFF_URL = (
    "https://raw.githubusercontent.com/pantherale0"
    "/pyanglianwater/refs/heads/main/charges.json?_"
)

AW_APP_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 4 XL Build/UQ1A.240205.004; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Version/4.0 Chrome/133.0.6943.49 Mobile Safari/537.36")
AW_APP_BASEURL = "https://apims-waf.awis.systems"
AW_APP_ENDPOINTS = {
    "get_app_state": {
        "method": "GET",
        "endpoint": "/myaccount/v1/state"
    },
    "get_account": {
        "method": "GET",
        "endpoint": "/myaccount/v1/accounts/{ACCOUNT_ID}"
    },
    "get_usage_details": {
        "method": "GET",
        "endpoint": "/myaccount/v1/accounts/{ACCOUNT_ID}/usage/smartmeter/frequency/{GRANULARITY}"
    },
    "get_account_summary": {
        "method": "GET",
        "endpoint": "/myaccount/v1/accounts/{ACCOUNT_ID}/billing/summary"
    }
}
AUTH_AW_BASE = "https://login.myaccount.anglianwater.co.uk"
AUTH_MSO_BASE = f"{AUTH_AW_BASE}/CustomerOnlineJourney.onmicrosoft.com/B2C_1A_SIGNUPORSIGNIN"
AUTH_MSO_CLIENT_ID = "7bba5f84-a1eb-4e58-9940-677a3d35598a"
AUTH_MSO_REDIR_URI = "uk.co.anglianwater.myaccount://oauth"
AUTH_MSO_SCOPES = [
    "https://customeronlinejourney.onmicrosoft.com/myaccount/api/access_as_user",
    "openid",
    "offline_access"
]
AUTH_MSO_CODE_CHALLENGE_METHOD = "S256"
AUTH_MSO_DEVICE_TYPE = "mobile"
AUTH_MSO_PLATFORM = "app"
AUTH_MSO_OS = "Android"
AUTH_MSO_APP_VERSION = "1.30.1"

AUTH_MSO_STEP_1_URL = (
    f"{AUTH_MSO_BASE}/oauth2/v2.0/authorize?client_id={AUTH_MSO_CLIENT_ID}"
    f"&response_type=code&redirect_uri={AUTH_MSO_REDIR_URI}"
    "&code_challenge={CODE_CHALLENGE}"
    f"&code_challenge_method={AUTH_MSO_CODE_CHALLENGE_METHOD}"
    f"&device_type={AUTH_MSO_DEVICE_TYPE}&platform={AUTH_MSO_PLATFORM}"
    f"&application_version={AUTH_MSO_APP_VERSION}&ui_locales=en"
    f"&scope={' '.join(AUTH_MSO_SCOPES)}"
    "&login_hint={EMAIL}"
)
AUTH_MSO_SELF_ASSERTED_URL = (
    f"{AUTH_MSO_BASE}/SelfAsserted?"
    "tx={STATE}&p=B2C_1A_SignUpOrSignIn"
)
AUTH_MSO_CONFIRM_URL = (
    f"{AUTH_MSO_BASE}/api/CombinedSigninAndSignup/confirmed?rememberMe=true&"
    "csrf_token={CSRF}&tx={STATE}&p=B2C_1A_SignUpOrSignIn"
)
AUTH_MSO_OAUTH_SERVICE = (
    "https://customeronlinejourney.b2clogin.com/customeronlinejourney.onmicrosoft.com/"
    "B2C_1A_SIGNUPORSIGNIN/oauth2/v2.0/"
)
AUTH_MSO_GET_TOKEN_URL = f"{AUTH_MSO_OAUTH_SERVICE}/token"
AUTH_MSO_REFRESH_TOKEN_URL = f"{AUTH_MSO_OAUTH_SERVICE}/refresh"

AW_ENCRYPTION_KEY = "d8ssmJ1c$qZq441%nC^u0!P!w96K@RdF"
AW_ENCRYPTION_SALT_SIZE = 16 # 128 bits
AW_ENCRYPTION_IV_SIZE = 16 # 128 bits
AW_ENCRYPTION_KEY_SIZE = 32 # 256 bits
AW_ENCRYPTION_ITERATIONS = 100
AW_ENCRYPTION_PBKDF2_HASH = "sha1"
