import os
import sys
import time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, User, Contact, Sequence, InstantlyCampaign
from app.services import settings_service, clients

db = SessionLocal()
user = db.query(User).first()
instantly_key = settings_service.get_key(db, user.id, "instantly")

# Find the row
row = db.query(InstantlyCampaign).filter(InstantlyCampaign.instantly_campaign_id == "0d1b7873-b524-4fab-9c00-cb73a0730b8c").first()
if row:
    seq = db.query(Sequence).filter(Sequence.id == row.sequence_id).first()
    print("Fetching leads for campaign", row.instantly_campaign_id)
    leads = clients.instantly_get_leads(instantly_key, row.instantly_campaign_id) or []
    for ld in leads:
        email = ld.get("email")
        status = ld.get("status")
        if not email or not status: continue
        contact = db.query(Contact).filter(Contact.email == email).first()
        if not contact:
            print(f"Creating contact for {email}")
            first = ld.get("first_name", "")
            last = ld.get("last_name", "")
            name = f"{first} {last}".strip() or email.split("@")[0]
            ref_contact = db.query(Contact).filter(Contact.id == seq.contact_id).first()
            experiment_id = ref_contact.source_ref if ref_contact else None
            account_id = ref_contact.account_id if ref_contact else None
            
            contact = Contact(
                email=email,
                full_name=name,
                strategy_id=seq.strategy_id,
                account_id=account_id,
                source_ref=experiment_id
            )
            db.add(contact)
            db.flush()
            
            new_seq = Sequence(
                contact_id=contact.id,
                strategy_id=seq.strategy_id,
                status="active",
                instantly_campaign_id=row.instantly_campaign_id
            )
            db.add(new_seq)
            db.flush()
            ic = InstantlyCampaign(
                sequence_id=new_seq.id,
                status="active",
                instantly_campaign_id=row.instantly_campaign_id
            )
            db.add(ic)
            db.flush()
            print(f"Created sequence {new_seq.id}")
db.commit()
print("Done")
