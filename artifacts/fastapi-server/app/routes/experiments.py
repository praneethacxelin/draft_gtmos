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
from app.agents.live_experiment import (
    promote_to_live,
    preview_promotion,
    launch_variant,
    compute_live_metrics,
    evaluate_live_batch,
    simulate_window,
    PromoteOptions,
)

router = APIRouter(prefix="/strategies/{strategy_id}/experiments", tags=["experiments"])


class SeedBatchRequest(BaseModel):
    n: int = 3
    leads_per_experiment: int = 10
    hypothesis: str | None = None
    strict_discovery: bool = True
    override_facets: dict | None = None


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
        strict_discovery=body.strict_discovery,
        override_facets=body.override_facets,
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


# ---------------------------------------------------------------------------
# Live (closed-loop) funnel test
# ---------------------------------------------------------------------------


class PromoteLiveRequest(BaseModel):
    draft_per_variant: int | None = None
    # Optional "real flow" configuration. Omitting any field keeps the original
    # promote behavior (materialize cohorts + draft 4-step sequences for all).
    auto_sequence: bool = True
    step_count: int = 4
    dynamic_templates: bool = False
    run_signals: bool = False
    score_leads: bool = False
    recognize_patterns: bool = False
    promote_tiers: list[int] | None = None


class LaunchVariantRequest(BaseModel):
    test_email: str | None = None


@router.post("/{batch_id}/promote-live")
async def promote_live(
    strategy_id: str,
    batch_id: str,
    body: PromoteLiveRequest | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Materialize real cohorts + draft sequences for every analyzed variant."""
    _own_batch(db, strategy_id, batch_id, user)
    tiers = body.promote_tiers if body else None
    options = PromoteOptions(
        draft_per_variant=(body.draft_per_variant if body and body.draft_per_variant else None),
        auto_sequence=body.auto_sequence if body else True,
        step_count=(body.step_count if body and body.step_count in (4, 5) else 4),
        dynamic_templates=body.dynamic_templates if body else False,
        run_signals=body.run_signals if body else False,
        score_leads=body.score_leads if body else False,
        recognize_patterns=body.recognize_patterns if body else False,
        promote_tiers=([t for t in tiers if t in (1, 2, 3)] or None) if tiers else None,
    )
    result = await promote_to_live(db, batch_id, options=options)
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=400, detail=result["_error"])
    return result


@router.get("/{batch_id}/promote-preview")
def promote_preview(
    strategy_id: str,
    batch_id: str,
    leads_per_variant: int | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Dry-run the promotion plan: how many leads each variant moves forward."""
    _own_batch(db, strategy_id, batch_id, user)
    result = preview_promotion(db, batch_id, draft_per_variant=leads_per_variant)
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=400, detail=result["_error"])
    return result


@router.post("/experiments/{experiment_id}/launch")
def launch_one_variant(
    strategy_id: str,
    experiment_id: str,
    body: LaunchVariantRequest | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Launch a variant's drafted sequences (engineer clicks send)."""
    _own_experiment(db, strategy_id, experiment_id, user)
    result = launch_variant(db, experiment_id, test_email=body.test_email if body else None)
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=400, detail=result["_error"])
    return result


@router.get("/{batch_id}/live")
def get_live(
    strategy_id: str,
    batch_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Live funnel metrics per variant for an in-flight test."""
    _own_batch(db, strategy_id, batch_id, user)
    result = compute_live_metrics(db, batch_id)
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=404, detail=result["_error"])
    return result


@router.post("/{batch_id}/evaluate-live")
def evaluate_live(
    strategy_id: str,
    batch_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Score the window and crown the live winner (only once it has closed)."""
    _own_batch(db, strategy_id, batch_id, user)
    result = evaluate_live_batch(db, batch_id, force=False)
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=400, detail=result["_error"])
    return result


@router.post("/{batch_id}/simulate-window")
def simulate_live_window(
    strategy_id: str,
    batch_id: str,
    db: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """TEST ONLY: synthesize the funnel + close the window so the loop can be
    observed without waiting the real window. Not part of the production flow."""
    _own_batch(db, strategy_id, batch_id, user)
    result = simulate_window(db, batch_id)
    if isinstance(result, dict) and "_error" in result:
        raise HTTPException(status_code=400, detail=result["_error"])
    return result
