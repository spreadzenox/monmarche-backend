"""Recipe endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import verify_api_token
from app.schemas.recipe import RecipeSummary
from app.services.notion_service import NotionService, NotionServiceError
from app.services.recipe_parser_service import RecipeParserService

router = APIRouter(prefix="/recipes", tags=["recipes"], dependencies=[Depends(verify_api_token)])


@router.get("", response_model=list[RecipeSummary])
def list_recipes() -> list[RecipeSummary]:
    try:
        notion = NotionService()
        recipes = notion.list_recipes()
    except NotionServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    parser = RecipeParserService()
    enriched: list[RecipeSummary] = []

    for recipe in recipes:
        try:
            detail = notion.get_recipe(recipe.id)
            parsed = parser.parse(detail.raw_content)
            enriched.append(recipe.model_copy(update={"servings": parsed.servings}))
        except NotionServiceError:
            enriched.append(recipe)

    return enriched
