"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.routes import auth, health, mappings, monmarche_auth, orders, recipes
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import SessionLocal, init_db
from app.services.recipe_cache_service import RecipeCacheService

logger = logging.getLogger(__name__)


def _refresh_recipe_cache_sync() -> None:
    db = SessionLocal()
    try:
        RecipeCacheService(db).sync_from_notion()
    except Exception as exc:
        logger.warning("Background recipe cache refresh failed: %s", exc)
    finally:
        db.close()


async def _recipe_cache_scheduler() -> None:
    settings = get_settings()
    while True:
        await asyncio.to_thread(_refresh_recipe_cache_sync)
        await asyncio.sleep(settings.recipes_cache_refresh_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    init_db()

    scheduler_task: asyncio.Task | None = None
    if get_settings().notion_configured:
        scheduler_task = asyncio.create_task(_recipe_cache_scheduler())

    yield

    if scheduler_task is not None:
        scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler_task


app = FastAPI(
    title="Mon Marché Meal Planner API",
    description="Backend for recipe selection, ingredient consolidation, and cart preparation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(recipes.router)
app.include_router(mappings.router)
app.include_router(orders.router)
app.include_router(monmarche_auth.router)
