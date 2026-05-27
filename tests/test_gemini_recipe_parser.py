"""Tests for Gemini-based recipe parsing."""

import json
from unittest.mock import MagicMock, patch

import httpx

from app.services.gemini_recipe_parser_service import GeminiRecipeParserService
from app.services.recipe_parser_service import RecipeParserService


GEMINI_RESPONSE = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "text": json.dumps(
                            {
                                "servings": 2,
                                "ingredients": [
                                    {
                                        "name": "avocat mûr",
                                        "quantity": 1,
                                        "unit": "piece",
                                        "optional": False,
                                        "raw_text": "1 avocat mûr",
                                    },
                                    {
                                        "name": "concombre",
                                        "quantity": 0.5,
                                        "unit": "piece",
                                        "optional": False,
                                        "raw_text": "1/2 concombre",
                                    },
                                ],
                                "instructions": ["Mélanger les ingrédients."],
                            }
                        )
                    }
                ]
            }
        }
    ]
}

MESSY_CONTENT = """
Portions : 2 personnes
Préparation : 15 min
1 avocat mûr
1/2 concombre
1. Égoutter les pois chiches.
Ingrédients à réutiliser : avocat, concombre.
"""


@patch("app.services.gemini_recipe_parser_service.get_settings")
@patch("app.services.gemini_recipe_parser_service.httpx.post")
def test_gemini_parser_returns_structured_ingredients(mock_post, mock_settings):
    mock_settings.return_value.gemini_api_key = "test-key"
    mock_settings.return_value.gemini_model = "gemini-2.0-flash"

    response = MagicMock(spec=httpx.Response)
    response.raise_for_status.return_value = None
    response.json.return_value = GEMINI_RESPONSE
    mock_post.return_value = response

    parsed = GeminiRecipeParserService().parse(MESSY_CONTENT, recipe_name="Salade avocat")

    assert parsed.servings == 2
    assert len(parsed.ingredients) == 2
    assert parsed.ingredients[0].name == "avocat mûr"
    assert parsed.instructions == ["Mélanger les ingrédients."]


@patch("app.services.recipe_parser_service.GeminiRecipeParserService")
def test_recipe_parser_prefers_gemini_when_configured(mock_gemini_cls):
    gemini = mock_gemini_cls.return_value
    gemini.configured = True
    gemini.parse.return_value = RecipeParserService()._parse_with_regex(
        "## Ingrédients\n1 oignon\n"
    )

    parsed = RecipeParserService().parse("content", recipe_name="Test")

    gemini.parse.assert_called_once()
    assert len(parsed.ingredients) == 1


def test_regex_parser_skips_metadata_lines():
    parsed = RecipeParserService()._parse_with_regex(MESSY_CONTENT)

    names = [item.name for item in parsed.ingredients]
    assert not any("Portions" in name for name in names)
    assert not any("Égoutter" in name for name in names)
    assert not any("reutiliser" in name.lower() for name in names)
