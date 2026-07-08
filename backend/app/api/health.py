from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.db.session import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "backend",
    }


@router.get("/ready")
def ready() -> JSONResponse:
    if not check_database_connection():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "service": "backend",
                "database": "unavailable",
            },
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ready",
            "service": "backend",
            "database": "ok",
        },
    )
