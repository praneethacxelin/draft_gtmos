"""Admin-only endpoints. Gated by ADMIN_PASSWORD; no end-user auth required.

- ``POST /admin/login`` — exchange the admin password for a token.
- ``GET  /admin/strategies`` — list every strategy across every user.
- ``GET  /admin/strategies/{id}`` — fetch any single strategy.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.admin_auth import expected_token, require_admin, verify_password
from app.db import Strategy, User, get_session


router = APIRouter(prefix="/admin", tags=["admin"])


class LoginBody(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginBody) -> dict:
    if not verify_password(body.password):
        raise HTTPException(401, "Invalid admin password")
    return {"token": expected_token()}


@router.get("/me")
def me(_: None = Depends(require_admin)) -> dict:
    return {"ok": True, "role": "admin"}


@router.get("/strategies")
def list_all_strategies(
    _: None = Depends(require_admin),
    db: Session = Depends(get_session),
) -> list[dict]:
    rows = (
        db.query(Strategy, User)
        .outerjoin(User, Strategy.user_id == User.id)
        .order_by(Strategy.created_at.desc())
        .all()
    )
    out: list[dict] = []
    for s, u in rows:
        out.append(
            {
                "id": s.id,
                "product_name": s.product_name,
                "description": s.description,
                "target_market": s.target_market,
                "pain_points_raw": s.pain_points_raw,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "owner": {
                    "user_id": s.user_id,
                    "email": (u.email if u else None),
                    "is_admin": (bool(u.is_admin) if u and hasattr(u, "is_admin") else False),
                },
            }
        )
    return out


@router.get("/strategies/{strategy_id}")
def get_any_strategy(
    strategy_id: str,
    _: None = Depends(require_admin),
    db: Session = Depends(get_session),
) -> dict:
    s = db.query(Strategy).filter(Strategy.id == strategy_id).first()
    if not s:
        raise HTTPException(404, "Strategy not found")
    u = db.query(User).filter(User.id == s.user_id).first() if s.user_id else None
    return {
        "id": s.id,
        "product_name": s.product_name,
        "description": s.description,
        "target_market": s.target_market,
        "pain_points_raw": s.pain_points_raw,
        "icp": s.icp_json,
        "personas": s.personas_json,
        "problems": s.problems_json,
        "naics": s.naics_json,
        "stakeholder_map": s.stakeholder_map_json,
        "use_cases": s.use_cases_json,
        "tam_sam_som": s.tam_sam_som_json,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "owner": {
            "user_id": s.user_id,
            "email": (u.email if u else None),
            "is_admin": (bool(u.is_admin) if u and hasattr(u, "is_admin") else False),
        },
    }
