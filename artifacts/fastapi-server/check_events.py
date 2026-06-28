import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, AuditLog

db = SessionLocal()
events = db.query(AuditLog).filter(AuditLog.event_type == 'pipeline').all()

for e in events[-20:]:
    print(f"[{e.event_type}] {e.summary}")
