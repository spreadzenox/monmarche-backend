"""Local cache for Notion recipes with periodic background refresh."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CachedRecipe
from app.db.repositories import CachedRecipeRepository
from app.schemas.recipe import RecipeCacheStatus, RecipeDetail, RecipeSummary
from app.services.notion_service import NotionService, NotionServiceError
from app.services.recipe_parser_service import RecipeParserService

logger = logging.getLogger(__name__)


@dataclass
class _SyncState:
    in_progress: bool = False
    last_synced_at: datetime | None = None
    last_error: str | None = None
    recipe_count: int = 0


_sync_state = _SyncState()
_sync_lock = threading.Lock()


class RecipeCacheService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._recipes = CachedRecipeRepository(db)
        self._parser = RecipeParserService()

    @staticmethod
    def is_sync_in_progress() -> bool:
        with _sync_lock:
            return _sync_state.in_progress

    def get_status(self) -> RecipeCacheStatus:
        with _sync_lock:
            in_progress = _sync_state.in_progress
            last_error = _sync_state.last_error
            last_synced_at = _sync_state.last_synced_at
            recipe_count = _sync_state.recipe_count

        if in_progress:
            status = "syncing"
        elif recipe_count == 0 and last_error:
            status = "failed"
        elif recipe_count == 0:
            status = "empty"
        elif last_error:
            status = "stale"
        else:
            status = "ready"

        if recipe_count == 0:
            recipe_count = self._recipes.count()
            last_synced_at = last_synced_at or self._recipes.latest_synced_at()

        return RecipeCacheStatus(
            status=status,
            recipe_count=recipe_count,
            last_synced_at=last_synced_at,
            sync_in_progress=in_progress,
            error_message=last_error,
        )

    def list_summaries(self) -> list[RecipeSummary]:
        return [self._to_summary(recipe) for recipe in self._recipes.list_all()]

    def get_recipe(self, notion_page_id: str) -> RecipeDetail:
        recipe = self._recipes.get_by_id(notion_page_id)
        if not recipe:
            raise NotionServiceError(
                f"Recipe '{notion_page_id.replace('-', '')}' not found in local cache."
            )
        return self._to_detail(recipe)

    def sync_from_notion(self) -> RecipeCacheStatus:
        settings = get_settings()
        if not settings.notion_configured:
            raise NotionServiceError(
                "Notion is not configured. Set NOTION_TOKEN and NOTION_RECIPES_DATABASE_ID."
            )

        with _sync_lock:
            if _sync_state.in_progress:
                return self.get_status()
            _sync_state.in_progress = True
            _sync_state.last_error = None

        try:
            notion = NotionService()
            summaries = notion.list_recipes()
            synced_at = datetime.now(UTC)
            cached_recipes: list[CachedRecipe] = []

            for summary in summaries:
                servings = summary.servings
                raw_content = ""
                try:
                    detail = notion.get_recipe(summary.id)
                    raw_content = detail.raw_content
                    parsed = self._parser.parse(detail.raw_content)
                    servings = parsed.servings
                except NotionServiceError as exc:
                    logger.warning("Skipping content for recipe %s: %s", summary.id, exc)

                cached_recipes.append(
                    CachedRecipe(
                        notion_page_id=summary.id.replace("-", ""),
                        name=summary.name,
                        status=summary.status,
                        rating=summary.rating,
                        tags=summary.tags,
                        servings=servings,
                        raw_content=raw_content,
                        synced_at=synced_at,
                    )
                )

            self._recipes.replace_all(cached_recipes)

            with _sync_lock:
                _sync_state.in_progress = False
                _sync_state.last_synced_at = synced_at
                _sync_state.recipe_count = len(cached_recipes)
                _sync_state.last_error = None

            logger.info("Recipe cache synced from Notion (%s recipes)", len(cached_recipes))
            return self.get_status()
        except Exception as exc:
            logger.exception("Recipe cache sync failed")
            with _sync_lock:
                _sync_state.in_progress = False
                _sync_state.last_error = str(exc)
            raise

    @staticmethod
    def _to_summary(recipe: CachedRecipe) -> RecipeSummary:
        return RecipeSummary(
            id=recipe.notion_page_id,
            name=recipe.name,
            status=recipe.status,
            rating=recipe.rating,
            tags=recipe.tags or [],
            servings=recipe.servings,
        )

    @staticmethod
    def _to_detail(recipe: CachedRecipe) -> RecipeDetail:
        return RecipeDetail(
            id=recipe.notion_page_id,
            name=recipe.name,
            status=recipe.status,
            rating=recipe.rating,
            tags=recipe.tags or [],
            servings=recipe.servings,
            raw_content=recipe.raw_content,
        )
