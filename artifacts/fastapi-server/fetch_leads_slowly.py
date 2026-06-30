import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, User, Sequence, Contact, EngagementEvent, QualificationRecord
from app.services import clients, settings_service

db = SessionLocal()
user = db.query(User).first()
instantly_key = settings_service.get_key(db, user.id, "instantly")
camp_id = "0d1b7873-b524-4fab-9c00-cb73a0730b8c"

print("Fetching leads for campaign", camp_id)
leads = clients.instantly_get_leads(instantly_key, camp_id) or []
print(f"Fetched {len(leads)} leads")

for ld in leads:
    email = ld.get("email")
    status = ld.get("status")
    
    # map Instantly V2 int statuses to strings
    if isinstance(status, int):
        if status == 1: status = "active"
        elif status == 2: status = "replied"
        elif status == 3: status = "interested"
        elif status == 4: status = "bounced"
    
    print(f"Lead {email} is {status}")
    if not email or not status: continue
    
    contact = db.query(Contact).filter(Contact.email == email).first()
    if not contact: continue
    
    seq = db.query(Sequence).filter(Sequence.contact_id == contact.id).first()
    if not seq: continue
    
    if status in ("interested", "replied", "meeting_booked"):
        exists = db.query(EngagementEvent).filter(
            EngagementEvent.contact_id == contact.id,
            EngagementEvent.channel == "email",
            EngagementEvent.event_type == "email_reply"
        ).first()
        
        if not exists:
            print(f"Creating email_reply for {email}")
            db.add(EngagementEvent(
                strategy_id=seq.strategy_id,
                contact_id=contact.id,
                account_id=contact.account_id,
                channel="email",
                event_type="email_reply",
                intent_contribution_score=10.0,
                metadata_json={"instantly_status": status, "lead_id": ld.get("id")}
            ))
            if status in ("interested", "meeting_booked"):
                q = db.query(QualificationRecord).filter(QualificationRecord.contact_id == contact.id).first()
                if q:
                    q.status = "sql" if status == "meeting_booked" else "mql"
                    q.reasoning = f"Instantly lead status changed to {status}"

db.commit()
print("Done")
db.close()
