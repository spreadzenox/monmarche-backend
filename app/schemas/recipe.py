"""Recipe API schemas."""

from pydantic import BaseModel, Field


class RecipeSummary(BaseModel):
    id: str
    name: str
    status: str | None = None
    rating: str | None = None
    tags: list[str] = Field(default_factory=list)
    servings: int | None = None


class RecipeDetail(RecipeSummary):
    raw_content: str = ""
