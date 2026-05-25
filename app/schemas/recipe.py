"""Recipe API schemas."""

from datetime import datetime

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


class RecipeCacheStatus(BaseModel):
    status: str
    recipe_count: int
    last_synced_at: datetime | None = None
    sync_in_progress: bool = False
    error_message: str | None = None
