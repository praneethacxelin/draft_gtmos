import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, ExperimentBatch
from app.agents.live_experiment import compute_live_metrics

db = SessionLocal()
batch = db.query(ExperimentBatch).order_by(ExperimentBatch.created_at.desc()).first()
metrics = compute_live_metrics(db, batch.id)
print("Metrics for batch:", batch.id)
print(metrics)
db.close()
