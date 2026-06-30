import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, EngagementEvent, Contact

db = SessionLocal()
print("EngagementEvents:")
for ev in db.query(EngagementEvent).filter(EngagementEvent.event_type == "email_reply").all():
    print(ev.id, ev.contact_id, ev.event_type)
    c = db.query(Contact).filter(Contact.id == ev.contact_id).first()
    if c:
        print("  -> Contact:", c.email, c.source, c.source_ref)
    else:
        print("  -> Contact not found!")
db.close()
