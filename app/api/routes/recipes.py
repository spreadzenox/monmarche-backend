"""Recipe endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import get_settings
from app.core.security import require_session
from app.schemas.recipe import RecipeCacheStatus, RecipeSummary
from app.services.notion_service import NotionServiceError
from app.services.recipe_cache_service import RecipeCacheService

router = APIRouter(prefix="/recipes", tags=["recipes"], dependencies=[Depends(require_session)])


@router.get("", response_model=list[RecipeSummary])
def list_recipes(db: Session = Depends(get_db)) -> list[RecipeSummary]:
    cache = RecipeCacheService(db)
    recipes = cache.list_summaries()
    if recipes:
        return recipes

    status_info = cache.get_status()
    if status_info.sync_in_progress:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recipe cache is syncing from Notion. Retry shortly.",
        )

    if not get_settings().notion_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notion is not configured.",
        )

    detail = status_info.error_message or "Recipe cache is empty."
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


@router.get("/cache-status", response_model=RecipeCacheStatus)
def get_recipe_cache_status(db: Session = Depends(get_db)) -> RecipeCacheStatus:
    return RecipeCacheService(db).get_status()


@router.post("/sync", response_model=RecipeCacheStatus)
def sync_recipes(db: Session = Depends(get_db)) -> RecipeCacheStatus:
    cache = RecipeCacheService(db)
    if cache.is_sync_in_progress():
        return cache.get_status()

    try:
        return cache.sync_from_notion()
    except NotionServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
