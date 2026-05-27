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
    mock_settings.return_value.gemini_configured = False
    notion = mock_notion_cls.return_value
    edited = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    notion.list_recipes.return_value = [
        RecipeSummary(id="recipe1", name="Salade", tags=["été"], notion_last_edited_at=edited),
    ]
    notion.get_recipe.return_value = RecipeDetail(
        id="recipe1",
        name="Salade",
        tags=["été"],
        raw_content="Ingrédients\n- tomates\nPortions : 2",
        notion_last_edited_at=edited,
    )

    status = RecipeCacheService(db_session).sync_from_notion()

    assert status.status == "ready"
    assert status.recipe_count == 1
    recipes = RecipeCacheService(db_session).list_summaries()
    assert recipes[0].name == "Salade"
    assert recipes[0].servings == 2


@patch("app.services.recipe_cache_service.get_settings")
@patch("app.services.recipe_cache_service.NotionService")
def test_sync_skips_fetch_and_parse_when_notion_unchanged(mock_notion_cls, mock_settings, db_session):
    mock_settings.return_value.notion_configured = True
    edited = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    db_session.add(
        CachedRecipe(
            notion_page_id="recipe1",
            name="Salade",
            tags=["été"],
            servings=2,
            raw_content="Ingrédients\n- tomates",
            raw_content_hash=RecipeCacheService._hash_content("Ingrédients\n- tomates"),
            parsed_recipe_json={
                "servings": 2,
                "ingredients": [
                    {
                        "name": "tomates",
                        "quantity": 2,
                        "unit": "piece",
                        "raw_text": "2 tomates",
                        "optional": False,
                    }
                ],
                "instructions": [],
            },
            notion_last_edited_at=edited,
            synced_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    notion = mock_notion_cls.return_value
    notion.list_recipes.return_value = [
        RecipeSummary(
            id="recipe1",
            name="Salade renommée",
            tags=["été", "frais"],
            notion_last_edited_at=edited,
        ),
    ]

    RecipeCacheService(db_session).sync_from_notion()

    notion.get_recipe.assert_not_called()
    stored = RecipeCacheService(db_session).get_recipe("recipe1")
    assert stored.name == "Salade renommée"
    assert stored.tags == ["été", "frais"]
    parsed = RecipeCacheService(db_session).get_parsed_recipe("recipe1")
    assert parsed.ingredients[0].name == "tomates"


@patch("app.services.recipe_cache_service.get_settings")
@patch("app.services.recipe_cache_service.NotionService")
def test_sync_reuses_parsed_json_when_content_hash_unchanged(mock_notion_cls, mock_settings, db_session):
    mock_settings.return_value.notion_configured = True
    mock_settings.return_value.gemini_configured = True
    old_edited = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    new_edited = datetime(2026, 5, 25, 13, 0, tzinfo=UTC)
    raw_content = "Ingrédients\n- tomates"
    db_session.add(
        CachedRecipe(
            notion_page_id="recipe1",
            name="Salade",
            servings=2,
            raw_content=raw_content,
            raw_content_hash=RecipeCacheService._hash_content(raw_content),
            parsed_recipe_json={
                "servings": 2,
                "ingredients": [
                    {
                        "name": "tomates",
                        "quantity": 2,
                        "unit": "piece",
                        "raw_text": "2 tomates",
                        "optional": False,
                    }
                ],
                "instructions": [],
            },
            notion_last_edited_at=old_edited,
            synced_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    notion = mock_notion_cls.return_value
    notion.list_recipes.return_value = [
        RecipeSummary(id="recipe1", name="Salade", notion_last_edited_at=new_edited),
    ]
    notion.get_recipe.return_value = RecipeDetail(
        id="recipe1",
        name="Salade",
        raw_content=raw_content,
        notion_last_edited_at=new_edited,
    )

    with patch("app.services.recipe_cache_service.RecipeParserService") as mock_parser_cls:
        mock_parser_cls.return_value.parse.side_effect = AssertionError("Gemini should not run")
        RecipeCacheService(db_session).sync_from_notion()

    notion.get_recipe.assert_called_once()
    parsed = RecipeCacheService(db_session).get_parsed_recipe("recipe1")
    assert parsed.ingredients[0].name == "tomates"


@patch("app.services.recipe_cache_service.get_settings")
@patch("app.services.recipe_cache_service.NotionService")
def test_sync_backfills_notion_timestamp_without_refetch(mock_notion_cls, mock_settings, db_session):
    mock_settings.return_value.notion_configured = True
    edited = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    db_session.add(
        CachedRecipe(
            notion_page_id="recipe1",
            name="Salade",
            servings=2,
            raw_content="Ingrédients\n- tomates",
            parsed_recipe_json={
                "servings": 2,
                "ingredients": [
                    {
                        "name": "tomates",
                        "quantity": 2,
                        "unit": "piece",
                        "raw_text": "2 tomates",
                        "optional": False,
                    }
                ],
                "instructions": [],
            },
            synced_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    notion = mock_notion_cls.return_value
    notion.list_recipes.return_value = [
        RecipeSummary(id="recipe1", name="Salade", notion_last_edited_at=edited),
    ]

    RecipeCacheService(db_session).sync_from_notion()

    notion.get_recipe.assert_not_called()
    stored = db_session.get(CachedRecipe, "recipe1")
    assert stored.notion_last_edited_at.replace(tzinfo=UTC) == edited
    assert stored.raw_content_hash == RecipeCacheService._hash_content("Ingrédients\n- tomates")


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
