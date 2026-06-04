import sys
from dotenv import load_dotenv
load_dotenv()
from app.db import SessionLocal, AuditLog

db = SessionLocal()
pipeline_logs = db.query(AuditLog).filter(AuditLog.event_type == 'pipeline_stage').all()
print(f"Total pipeline stages globally: {len(pipeline_logs)}")
for log in pipeline_logs[:10]:
    print(f"- {log.strategy_name} | {log.service} | {log.summary.encode('ascii', 'ignore').decode()}")
