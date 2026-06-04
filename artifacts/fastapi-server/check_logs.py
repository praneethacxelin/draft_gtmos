import sys
import requests
from dotenv import load_dotenv
load_dotenv()
from app.db import SessionLocal, Strategy

db = SessionLocal()
s = db.query(Strategy).filter(Strategy.product_name.like("%PulseSignal%")).first()

print(f"Testing Discover Leads for {s.id}")
res = requests.post(f"http://localhost:8080/api/strategies/{s.id}/leads/search", stream=True)
print(f"Status: {res.status_code}")
if res.status_code != 200:
    print(res.text)
else:
    for line in res.iter_lines():
        if line:
            print(line.decode())






