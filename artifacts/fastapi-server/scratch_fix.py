import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Add the project root to sys.path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db import SessionLocal, ExperimentBatch, Experiment, Contact, Sequence

db = SessionLocal()
# Find any drafted batch
batches = db.query(ExperimentBatch).filter(ExperimentBatch.live_status == 'drafted').all()

for batch in batches:
    print(f"Fixing batch {batch.id}...")
    experiments = db.query(Experiment).filter(Experiment.batch_id == batch.id).order_by(Experiment.idx.asc()).all()
    
    total_to_promote = 0
    total_available = 0
    variants = []
    
    for exp in experiments:
        cohort = db.query(Contact).filter(Contact.source_ref == exp.id).all()
        cohort_size = len(cohort)
        
        drafted_now = 0
        for c in cohort:
            if db.query(Sequence).filter(Sequence.contact_id == c.id).first():
                drafted_now += 1
                
        total_to_promote += cohort_size
        available = len(exp.leads_json or [])
        total_available += available
        
        is_winner = batch.best_experiment_id == exp.id
        
        variants.append({
            "experiment_id": exp.id,
            "name": exp.name,
            "cohort_size": cohort_size,
            "drafted_now": drafted_now,
            "relevancy": None,
            "is_winner": is_winner,
            "planned": cohort_size,
            "available_leads": available,
            "idx": exp.idx,
            "skipped": cohort_size == 0
        })

    snapshot = batch.analysis_json.copy() if isinstance(batch.analysis_json, dict) else {}
    snapshot["live_cohort"] = {
        "total_to_promote": total_to_promote,
        "total_available": total_available,
        "budget_per_variant": 25,
        "variants": variants,
    }
    # SQLAlchemy JSONB mutation trick
    batch.analysis_json = None
    db.commit()
    batch.analysis_json = snapshot
    db.commit()
    print("Fixed!")

print("Done")
