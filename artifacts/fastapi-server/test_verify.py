import os
from dotenv import load_dotenv
load_dotenv('.env')

import httpx

api_key = os.environ.get("INSTANTLY_API_KEY")

url = "https://api.instantly.ai/api/v2/email-verification"
headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}

r = httpx.post(url, json={"email": "test@example.com"}, headers=headers)
print("Status Code:", r.status_code)
print("Response:", r.text)
