"""Local cache for Notion recipes with periodic background refresh."""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CachedRecipe
from app.db.repositories import CachedRecipeRepository
from app.schemas.ingredient import ParsedRecipe
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


@dataclass
class _SyncStats:
    reused_unchanged: int = 0
    reused_hash: int = 0
    reparsed: int = 0
    fetched: int = 0


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

    def get_parsed_recipe(self, notion_page_id: str) -> ParsedRecipe:
        recipe = self._recipes.get_by_id(notion_page_id)
        if not recipe:
            raise NotionServiceError(
                f"Recipe '{notion_page_id.replace('-', '')}' not found in local cache."
            )
        if recipe.parsed_recipe_json:
            return ParsedRecipe.model_validate(recipe.parsed_recipe_json)
        return self._parser.parse(recipe.raw_content, recipe_name=recipe.name)

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
            existing_by_id = {recipe.notion_page_id: recipe for recipe in self._recipes.list_all()}
            synced_at = datetime.now(UTC)
            cached_recipes: list[CachedRecipe] = []
            stats = _SyncStats()

            for summary in summaries:
                page_id = summary.id.replace("-", "")
                existing = existing_by_id.get(page_id)
                cached_recipes.append(
                    self._sync_recipe(
                        notion=notion,
                        summary=summary,
                        existing=existing,
                        synced_at=synced_at,
                        stats=stats,
                    )
                )

            self._recipes.replace_all(cached_recipes)

            with _sync_lock:
                _sync_state.in_progress = False
                _sync_state.last_synced_at = synced_at
                _sync_state.recipe_count = len(cached_recipes)
                _sync_state.last_error = None

            logger.info(
                "Recipe cache synced (%s recipes): unchanged=%s hash_reuse=%s reparsed=%s fetched=%s",
                len(cached_recipes),
                stats.reused_unchanged,
                stats.reused_hash,
                stats.reparsed,
                stats.fetched,
            )
            return self.get_status()
        except Exception as exc:
            logger.exception("Recipe cache sync failed")
            with _sync_lock:
                _sync_state.in_progress = False
                _sync_state.last_error = str(exc)
            raise

    def _sync_recipe(
        self,
        *,
        notion: NotionService,
        summary: RecipeSummary,
        existing: CachedRecipe | None,
        synced_at: datetime,
        stats: _SyncStats,
    ) -> CachedRecipe:
        page_id = summary.id.replace("-", "")

        if self._can_reuse_unchanged(existing, summary):
            stats.reused_unchanged += 1
            return self._build_cached_recipe(
                summary=summary,
                synced_at=synced_at,
                raw_content=existing.raw_content,
                raw_content_hash=self._content_hash(existing),
                parsed_json=existing.parsed_recipe_json,
                servings=existing.servings,
                notion_last_edited_at=existing.notion_last_edited_at,
            )

        if self._can_backfill_from_list(existing, summary):
            stats.reused_unchanged += 1
            return self._build_cached_recipe(
                summary=summary,
                synced_at=synced_at,
                raw_content=existing.raw_content,
                raw_content_hash=self._content_hash(existing),
                parsed_json=existing.parsed_recipe_json,
                servings=existing.servings,
                notion_last_edited_at=summary.notion_last_edited_at,
            )

        servings = summary.servings
        raw_content = ""
        parsed_json = None
        content_hash = None
        notion_last_edited_at = summary.notion_last_edited_at

        try:
            detail = self._fetch_recipe_with_retry(notion, summary.id)
            stats.fetched += 1
            raw_content = detail.raw_content
            content_hash = self._hash_content(raw_content)
            notion_last_edited_at = summary.notion_last_edited_at or detail.notion_last_edited_at

            if self._can_reuse_parsed(existing, content_hash, raw_content):
                stats.reused_hash += 1
                parsed_json = existing.parsed_recipe_json
                servings = existing.servings
            else:
                stats.reparsed += 1
                parsed = self._parser.parse(raw_content, recipe_name=summary.name)
                servings = parsed.servings
                parsed_json = parsed.model_dump()
                if get_settings().gemini_configured:
                    time.sleep(0.4)
        except NotionServiceError as exc:
            logger.warning("Skipping content for recipe %s: %s", summary.id, exc)
            if existing:
                raw_content = existing.raw_content
                content_hash = existing.raw_content_hash
                parsed_json = existing.parsed_recipe_json
                servings = existing.servings
                notion_last_edited_at = existing.notion_last_edited_at

        return self._build_cached_recipe(
            summary=summary,
            synced_at=synced_at,
            raw_content=raw_content,
            raw_content_hash=content_hash,
            parsed_json=parsed_json,
            servings=servings,
            notion_last_edited_at=notion_last_edited_at,
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _can_reuse_unchanged(existing: CachedRecipe | None, summary: RecipeSummary) -> bool:
        if not existing or not existing.parsed_recipe_json or not existing.raw_content:
            return False
        existing_at = RecipeCacheService._normalize_datetime(existing.notion_last_edited_at)
        summary_at = RecipeCacheService._normalize_datetime(summary.notion_last_edited_at)
        if not summary_at or not existing_at:
            return False
        return existing_at == summary_at

    @staticmethod
    def _can_backfill_from_list(existing: CachedRecipe | None, summary: RecipeSummary) -> bool:
        if not existing or not existing.parsed_recipe_json or not existing.raw_content:
            return False
        if existing.notion_last_edited_at is not None:
            return False
        return summary.notion_last_edited_at is not None

    @staticmethod
    def _content_hash(existing: CachedRecipe | None, content: str | None = None) -> str | None:
        if existing and existing.raw_content_hash:
            return existing.raw_content_hash
        source = content if content is not None else (existing.raw_content if existing else "")
        if not source:
            return None
        return RecipeCacheService._hash_content(source)

    @staticmethod
    def _can_reuse_parsed(
        existing: CachedRecipe | None,
        content_hash: str | None,
        raw_content: str | None = None,
    ) -> bool:
        if not existing or not existing.parsed_recipe_json or not content_hash:
            return False
        existing_hash = RecipeCacheService._content_hash(existing, raw_content)
        return existing_hash == content_hash

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_cached_recipe(
        *,
        summary: RecipeSummary,
        synced_at: datetime,
        raw_content: str,
        raw_content_hash: str | None,
        parsed_json: dict | None,
        servings: int | None,
        notion_last_edited_at: datetime | None,
    ) -> CachedRecipe:
        return CachedRecipe(
            notion_page_id=summary.id.replace("-", ""),
            name=summary.name,
            status=summary.status,
            rating=summary.rating,
            tags=summary.tags,
            servings=servings,
            raw_content=raw_content,
            raw_content_hash=raw_content_hash,
            parsed_recipe_json=parsed_json,
            notion_last_edited_at=notion_last_edited_at,
            synced_at=synced_at,
        )

    @staticmethod
    def _fetch_recipe_with_retry(notion: NotionService, recipe_id: str, attempts: int = 3):
        last_error: NotionServiceError | None = None
        for attempt in range(attempts):
            try:
                return notion.get_recipe(recipe_id)
            except NotionServiceError as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(2**attempt)
        if last_error:
            raise last_error
        raise NotionServiceError(f"Unable to fetch recipe '{recipe_id}'.")

    @staticmethod
    def _to_summary(recipe: CachedRecipe) -> RecipeSummary:
        return RecipeSummary(
            id=recipe.notion_page_id,
            name=recipe.name,
            status=recipe.status,
            rating=recipe.rating,
            tags=recipe.tags or [],
            servings=recipe.servings,
            notion_last_edited_at=recipe.notion_last_edited_at,
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
            notion_last_edited_at=recipe.notion_last_edited_at,
        )
