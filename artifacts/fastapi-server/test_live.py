import os
import sys
import json
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, ExperimentBatch
from app.agents.live_experiment import compute_live_metrics

db = SessionLocal()
batch = db.query(ExperimentBatch).filter(ExperimentBatch.live_status == 'running').first()
res = compute_live_metrics(db, batch.id)
print(json.dumps(res, indent=2))
