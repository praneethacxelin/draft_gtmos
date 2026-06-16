"""Experiments API — Apollo parameter pattern search per product profile."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_session, ExperimentBatch, Experiment, User
from app.auth import current_user
from app.scoping import own_strategy
from app.agents.experiments import (
    seed_batch,
    run_experiment,
    run_batch,
    analyze_batch,
    sanitize_params,
    serialize_batch,
    serialize_experiment,
)

router = APIRouter(prefix="/strategies/{strategy_id}/experiments", tags=["experiments"])


class SeedBatchRequest(BaseModel):
    n: int = 3
    leads_per_experiment: int = 10
    hypothesis: str | None = None


class ExperimentParamsPatch(BaseModel):
    name: str | None = None
    hypothesis: str | None = None
    params: dict | None = None


def _own_batch(db: Session, strategy_id: str, batch_id: str, user: User) -> ExperimentBatch:
    own_strategy(db, strategy_id, user)
    batch = (
        db.query(ExperimentBatch)
        .filter(
            ExperimentBatch.id == batch_id,
            ExperimentBatch.strategy_id == strategy_id,
        )
        .first()
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Experiment batch not found")
    return batch


def _own_experiment(db: Session, strategy_id: str, experiment_id: str, user: User) -> Experiment:
    own_strategy(db, strategy_id, user)
    exp = (
        db.query(Experiment)
        .filter(
            Experiment.id == experiment_id,
            Experiment.strategy_id == strategy_id,
        )
        .first()
    )
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@router.get("")
def list_batches(
    strategy_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[dict]:
    own_strategy(db, strategy_id, user)
    rows = (
        db.query(ExperimentBatch)
        .filter(ExperimentBatch.strategy_id == strategy_id)
        .order_by(ExperimentBatch.created_at.desc())
        .all()
    )
    return [serialize_batch(db, b) for b in rows]


@router.get("/{batch_id}")
def get_batch(
    strategy_id: str,
    batch_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    batch = _own_batch(db, strategy_id, batch_id, user)
    return serialize_batch(db, batch)


@router.post("")
async def create_batch(
    strategy_id: str,
    body: SeedBatchRequest,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    own_strategy(db, strategy_id, user)
    result = await seed_batch(
        db,
        strategy_id,
        n=body.n,
        leads_per_experiment=body.leads_per_experiment,
        hypothesis=body.hypothesis,
    )
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=502, detail=result["_error"])
    return result


@router.delete("/{batch_id}")
def delete_batch(
    strategy_id: str,
    batch_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    batch = _own_batch(db, strategy_id, batch_id, user)
    db.delete(batch)
    db.commit()
    return {"ok": True}


@router.patch("/experiments/{experiment_id}")
def patch_experiment(
    strategy_id: str,
    experiment_id: str,
    body: ExperimentParamsPatch,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    exp = _own_experiment(db, strategy_id, experiment_id, user)
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        exp.name = changes["name"]
    if "hypothesis" in changes:
        exp.hypothesis = changes["hypothesis"]
    if "params" in changes and changes["params"] is not None:
        exp.params_json = sanitize_params(changes["params"])
        exp.source = "user"
    db.commit()
    db.refresh(exp)
    return serialize_experiment(exp)


@router.post("/experiments/{experiment_id}/run")
async def run_one(
    strategy_id: str,
    experiment_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    _own_experiment(db, strategy_id, experiment_id, user)
    result = await run_experiment(db, experiment_id)
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=502, detail=result["_error"])
    return result


@router.post("/{batch_id}/run")
async def run_all(
    strategy_id: str,
    batch_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    _own_batch(db, strategy_id, batch_id, user)
    result = await run_batch(db, batch_id)
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=502, detail=result["_error"])
    return result


@router.post("/{batch_id}/analyze")
async def analyze(
    strategy_id: str,
    batch_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    _own_batch(db, strategy_id, batch_id, user)
    result = await analyze_batch(db, batch_id)
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=400, detail=result["_error"])
    return result
