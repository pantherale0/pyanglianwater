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

ANGLIAN_WATER_AREAS = {
    "Anglian": {
        "Standard": {
            "rate": 2.0954,
            "service": 37.00
        },
        "LITE": {
            "rate": 1.5716,
            "service": 27.75
        },
        "AquaCare Plus": {
            "rate": 1.0087,
            "service": 118.50
        },
        "Extra LITE": {
            "rate": 1.0477,
            "service": 18.50
        },
        "LITE 60": {
            "rate": 0.8382,
            "service": 14.80
        },
        "LITE 80": {
            "rate": 0.4191,
            "service": 7.40
        },
        "WaterSure": {
            "rate": 241,
            "interval_mode": True,
            "interval": "year"
        },
        "Custom": {
            "custom": True,
            "rate": 0.0
        }
    },
    "Hartlepool": {
        "Standard": {
            "rate": 1.2195,
            "service": 31.50
        },
        "LITE": {
            "rate": 0.9146,
            "service": 23.60
        },
        "AquaCare Plus": {
            "rate": 0.7128,
            "service": 69.50
        },
        "Extra LITE": {
            "rate": 0.6098,
            "service": 15.75
        },
        "LITE 60": {
            "rate": 0.4878,
            "service": 12.60
        },
        "LITE 80": {
            "rate": 0.2439,
            "service": 6.30
        },
        "WaterSure": {
            "rate": 144,
            "interval_mode": True,
            "interval": "year"
        },
        "Custom": {
            "custom": True,
            "rate": 0.0
        }
    },
    "Finningley": {
        "Standard": {
            "custom": True,
            "rate": 0.0
        }
    },
    "Northstowe": {
        "Everyday": {
            "rate": 1.1053,
            "service": 47.28
        },
        "WaterSure": {
            "rate": 164.69,
            "interval_mode": True,
            "interval": "year"
        },
        "LITE": {
            "rate": 0.8290,
            "service": 35.45
        },
        "Extra LITE": {
            "rate": 0.5527,
            "service": 23.60
        },
        "Custom": {
            "custom": True,
            "rate": 0.0
        }
    },
    "Woods Meadow": {}
}
