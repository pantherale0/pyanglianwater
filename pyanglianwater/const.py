"""Anglian Water consts."""

API_BASEURL = "https://my.anglianwater.co.uk/mobile/api"

API_ENDPOINTS = {
    "login": {
        "method": "POST",
        "endpoint": "/Login"
    },
    "register_device": {
        "method": "POST",
        "endpoint": "/UpdateProfileSetupSAP"
    },
    "get_dashboard_details": {
        "method": "POST",
        "endpoint": "/GetDashboardDetails"
    },
    "get_bills_payments": {
        "method": "POST",
        "endpoint": "/GetBillsAndPayments"
    },
    "get_usage_details": {
        "method": "POST",
        "endpoint": "/GetMyUsagesDetailsFromAWBI"
    }
}


API_APP_KEY = "2.7$1.9.3$Android$samsung$SM-N9005$11"
API_PARTNER_KEY = "Mobile${EMAIL}${ACC_NO}${DEV_ID}${APP_KEY}"

ANGLIAN_WATER_TARIFFS = {
    "standard": {
        "rate": 2.0954
    },
    "LITE": {
        "rate": 0.0,
        "custom": True
    },
    "AquaCare": {
        "rate": 1.0087
    },
    "WaterSure": {
        "rate": 241,
        "interval_mode": True,
        "interval": "year"
    }
}
