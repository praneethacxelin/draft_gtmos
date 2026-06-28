import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, Sequence, Contact, ExperimentBatch, Experiment

db = SessionLocal()
batch = db.query(ExperimentBatch).filter(ExperimentBatch.live_status == 'running').first()
if not batch:
    batch = db.query(ExperimentBatch).filter(ExperimentBatch.live_status == 'drafted').first()

if not batch:
    print("No live/drafted batch found.")
    sys.exit(0)

print(f"Batch {batch.id}")
experiments = db.query(Experiment).filter(Experiment.batch_id == batch.id).all()
for exp in experiments:
    contacts = db.query(Contact).filter(Contact.source_ref == exp.id).all()
    c_ids = [c.id for c in contacts]
    if c_ids:
        seqs = db.query(Sequence).filter(Sequence.contact_id.in_(c_ids)).all()
        active = sum(1 for s in seqs if s.status in ('active', 'simulated', 'sent'))
        print(f"Exp {exp.name}: {len(contacts)} contacts, {len(seqs)} seqs, {active} active seqs")
    else:
        print(f"Exp {exp.name}: 0 contacts")
