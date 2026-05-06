from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
def health() -> dict:
    return {"status": "ok"}
