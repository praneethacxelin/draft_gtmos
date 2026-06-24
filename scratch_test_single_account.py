import os
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "artifacts", "fastapi-server", ".env"))
api_key = os.environ.get("INSTANTLY_API_KEY")

if api_key:
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client() as client:
        email = "jayavardhan1810@gmail.com"
        r = client.get(f"https://api.instantly.ai/api/v2/accounts/{email}", headers=headers)
        print("Status Code for email path:", r.status_code)
        if r.status_code == 200:
            print("Response:", r.json())
        else:
            print("Error Response:", r.text)
