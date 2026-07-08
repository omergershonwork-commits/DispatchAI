from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "backend",
    }


@router.get("/ready")
def ready() -> dict[str, str]:
    return {
        "status": "ready",
        "service": "backend",
    }