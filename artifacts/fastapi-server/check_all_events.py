import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, EngagementEvent

db = SessionLocal()
print("All EngagementEvents:")
for ev in db.query(EngagementEvent).all():
    print(ev.id, ev.contact_id, ev.event_type, ev.metadata_json)
db.close()
