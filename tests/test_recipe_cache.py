"""Tests for the local Notion recipe cache."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import CachedRecipe
from app.schemas.recipe import RecipeDetail, RecipeSummary
from app.services.recipe_cache_service import RecipeCacheService, _sync_state, _sync_lock


@pytest.fixture(autouse=True)
def reset_sync_state():
    with _sync_lock:
        _sync_state.in_progress = False
        _sync_state.last_synced_at = None
        _sync_state.last_error = None
        _sync_state.recipe_count = 0


def test_list_summaries_reads_from_database(db_session):
    db_session.add(
        CachedRecipe(
            notion_page_id="abc123",
            name="Pâtes carbonara",
            status="Publié",
            rating="5",
            tags=["rapide"],
            servings=4,
            raw_content="Ingrédients\n- pâtes",
            synced_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    recipes = RecipeCacheService(db_session).list_summaries()

    assert len(recipes) == 1
    assert recipes[0] == RecipeSummary(
        id="abc123",
        name="Pâtes carbonara",
        status="Publié",
        rating="5",
        tags=["rapide"],
        servings=4,
    )


def test_get_recipe_returns_cached_detail(db_session):
    db_session.add(
        CachedRecipe(
            notion_page_id="abc123",
            name="Pâtes carbonara",
            raw_content="Ingrédients\n- pâtes",
            synced_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    recipe = RecipeCacheService(db_session).get_recipe("abc123")

    assert recipe.raw_content == "Ingrédients\n- pâtes"
    assert recipe.name == "Pâtes carbonara"


@patch("app.services.recipe_cache_service.get_settings")
@patch("app.services.recipe_cache_service.NotionService")
def test_sync_from_notion_replaces_cache(mock_notion_cls, mock_settings, db_session):
    mock_settings.return_value.notion_configured = True
    notion = mock_notion_cls.return_value
    notion.list_recipes.return_value = [
        RecipeSummary(id="recipe-1", name="Salade", tags=["été"]),
    ]
    notion.get_recipe.return_value = RecipeDetail(
        id="recipe-1",
        name="Salade",
        tags=["été"],
        raw_content="Ingrédients\n- tomates\nPortions : 2",
    )

    status = RecipeCacheService(db_session).sync_from_notion()

    assert status.status == "ready"
    assert status.recipe_count == 1
    recipes = RecipeCacheService(db_session).list_summaries()
    assert recipes[0].name == "Salade"
    assert recipes[0].servings == 2


def test_list_recipes_endpoint_uses_cache(auth_client, db_session):
    db_session.add(
        CachedRecipe(
            notion_page_id="cached-1",
            name="Soupe",
            synced_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    response = auth_client.get("/recipes")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Soupe"


def test_cache_status_endpoint(auth_client, db_session):
    db_session.add(
        CachedRecipe(
            notion_page_id="cached-1",
            name="Soupe",
            synced_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    response = auth_client.get("/recipes/cache-status")

    assert response.status_code == 200
    body = response.json()
    assert body["recipe_count"] == 1
    assert body["sync_in_progress"] is False
