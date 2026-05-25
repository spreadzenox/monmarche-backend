"""Ingredient scaling and consolidation across recipes."""

from __future__ import annotations

from app.schemas.ingredient import ConsolidatedIngredient, ParsedIngredient, UncertainIngredient
from app.services.normalization_service import NormalizationService


class IngredientService:
    """Scale recipe ingredients and merge duplicates."""

    def __init__(self, normalization_service: NormalizationService | None = None) -> None:
        self._normalization = normalization_service or NormalizationService()

    def scale_ingredients(
        self,
        ingredients: list[ParsedIngredient],
        *,
        recipe_servings: int,
        people_count: int,
    ) -> tuple[list[ParsedIngredient], list[UncertainIngredient]]:
        if recipe_servings <= 0:
            recipe_servings = 2

        factor = people_count / recipe_servings
        scaled: list[ParsedIngredient] = []
        uncertain: list[UncertainIngredient] = []

        for ingredient in ingredients:
            if ingredient.quantity is None:
                uncertain.append(
                    UncertainIngredient(
                        raw_text=ingredient.raw_text,
                        reason="quantity_not_detected",
                    )
                )
                scaled.append(ingredient)
                continue

            scaled.append(
                ParsedIngredient(
                    name=ingredient.name,
                    quantity=ingredient.quantity * factor,
                    unit=ingredient.unit,
                    raw_text=ingredient.raw_text,
                    optional=ingredient.optional,
                )
            )

        return scaled, uncertain

    def consolidate(
        self,
        ingredient_groups: list[list[ParsedIngredient]],
    ) -> tuple[list[ConsolidatedIngredient], list[UncertainIngredient]]:
        merged: dict[tuple[str, str | None], ConsolidatedIngredient] = {}
        uncertain: list[UncertainIngredient] = []

        for ingredients in ingredient_groups:
            for ingredient in ingredients:
                normalized_name = self._normalization.normalize(ingredient.name)
                display_name = ingredient.name.strip() or normalized_name

                if ingredient.quantity is None or ingredient.unit is None:
                    uncertain.append(
                        UncertainIngredient(
                            raw_text=ingredient.raw_text,
                            reason="quantity_not_detected" if ingredient.quantity is None else "unit_not_detected",
                        )
                    )
                    key = (normalized_name, ingredient.unit)
                    if key not in merged:
                        merged[key] = ConsolidatedIngredient(
                            name=display_name,
                            normalized_name=normalized_name,
                            required_quantity=None,
                            unit=ingredient.unit,
                            raw_text=ingredient.raw_text,
                            optional=ingredient.optional,
                        )
                    continue

                key = (normalized_name, ingredient.unit)
                if key in merged and merged[key].required_quantity is not None:
                    merged[key].required_quantity += ingredient.quantity
                    if len(display_name) > len(merged[key].name):
                        merged[key].name = display_name
                else:
                    merged[key] = ConsolidatedIngredient(
                        name=display_name,
                        normalized_name=normalized_name,
                        required_quantity=ingredient.quantity,
                        unit=ingredient.unit,
                        raw_text=ingredient.raw_text,
                        optional=ingredient.optional,
                    )

        return list(merged.values()), uncertain
