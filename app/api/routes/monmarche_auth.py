"""Mon Marché session helper endpoints."""

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import require_session

router = APIRouter(
    prefix="/monmarche",
    tags=["monmarche"],
    dependencies=[Depends(require_session)],
)


@router.get("/session-status")
def monmarche_session_status() -> dict[str, object]:
    settings = get_settings()
    storage_path = settings.monmarche_storage_state_file
    return {
        "session_exists": storage_path.exists(),
        "storage_state_path": str(storage_path),
        "cart_url": settings.monmarche_cart_url,
        "message": (
            "Session ready"
            if storage_path.exists()
            else "Run python scripts/save_monmarche_session.py to create a session"
        ),
    }
