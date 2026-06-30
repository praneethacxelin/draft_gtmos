import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, Contact

db = SessionLocal()
count = 0
for contact in db.query(Contact).filter(Contact.source_ref.isnot(None), Contact.source != "experiment").all():
    contact.source = "experiment"
    count += 1
db.commit()
db.close()
print(f"Updated {count} contacts to source='experiment'")
