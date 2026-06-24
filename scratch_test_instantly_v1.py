import os
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "artifacts", "fastapi-server", ".env"))
api_key = os.environ.get("INSTANTLY_API_KEY")

if api_key:
    with httpx.Client() as client:
        # Test v1 accounts list
        r = client.get(f"https://api.instantly.ai/api/v1/account/list?api_key={api_key}")
        print("v1 Status Code:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                print("First v1 Account Keys:", list(data[0].keys()))
                print("First v1 Account Data:", data[0])
            else:
                print("v1 Response:", data)
        else:
            print("v1 Error:", r.text)
