"""Ingredient schemas."""

from pydantic import BaseModel, Field


class ParsedIngredient(BaseModel):
    name: str
    quantity: float | None = None
    unit: str | None = None
    raw_text: str
    optional: bool = False


class ParsedRecipe(BaseModel):
    servings: int = 2
    ingredients: list[ParsedIngredient] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)


class ConsolidatedIngredient(BaseModel):
    name: str
    normalized_name: str
    required_quantity: float | None = None
    unit: str | None = None
    raw_text: str | None = None
    optional: bool = False


class UncertainIngredient(BaseModel):
    raw_text: str
    reason: str


class PreviewIngredient(BaseModel):
    name: str
    normalized_name: str
    required_quantity: float | None = None
    unit: str | None = None
