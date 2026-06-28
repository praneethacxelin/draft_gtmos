import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, User, Contact, Sequence, InstantlyCampaign
from app.services import settings_service, clients

db = SessionLocal()
user = db.query(User).first()
instantly_key = settings_service.get_key(db, user.id, "instantly")

ws_camps = clients.instantly_get_campaigns(instantly_key) or []
print(f"Total Instantly campaigns: {len(ws_camps)}")
for c in ws_camps:
    cid = c.get("id")
    print(f"Campaign: {c.get('name')} ({cid})")
    leads = clients.instantly_get_leads(instantly_key, cid) or []
    for ld in leads:
        email = ld.get("email")
        print(f"  Lead: {email}, status: {ld.get('status')}")
