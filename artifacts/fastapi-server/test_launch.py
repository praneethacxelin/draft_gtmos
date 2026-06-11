import os
from dotenv import load_dotenv
load_dotenv('.env')

import httpx

api_key = os.environ.get("INSTANTLY_API_KEY")
url = "https://api.instantly.ai/api/v2/campaigns"
headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}

body = {
    "name": "Test Campaign",
    "sequences": [
        {
            "steps": [
                {
                    "type": "email",
                    "subject": "Test",
                    "content": "Hello",
                    "wait_days": 1
                }
            ]
        }
    ],
    "campaign_schedule": {
        "schedules": [
            {
                "name": "Custom UI Schedule",
                "timing": {"from": "09:00", "to": "17:00"},
                "timezone": "UTC",
                "days": ["Mon", "Tue", "Wed", "Thu", "Fri"]
            }
        ]
    }
}

r = httpx.post(url, json=body, headers=headers)
print("Status Code:", r.status_code)
print("Response:", r.text)
