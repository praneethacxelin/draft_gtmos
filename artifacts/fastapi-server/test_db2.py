import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, Contact

db = SessionLocal()
emails = ["saipraneethacxelinagentix@gmail.com", "praneeth@acxelinagentix.com", "jayavardhan@acxelinagentix.com", "sarah@acxelinagentix.com"]
for e in emails:
    c = db.query(Contact).filter(Contact.email == e).first()
    if c:
        print(f"{e} is in DB, source_ref={c.source_ref}")
    else:
        print(f"{e} NOT in DB")
