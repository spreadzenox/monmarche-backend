from app.schemas.ingredient import ParsedIngredient
from app.services.ingredient_service import IngredientService


def test_scale_and_consolidate_ingredients():
    service = IngredientService()

    recipe_a = [
        ParsedIngredient(name="tomates", quantity=2, unit="piece", raw_text="2 tomates"),
    ]
    recipe_b = [
        ParsedIngredient(name="Tomates", quantity=4, unit="piece", raw_text="4 tomates"),
    ]

    scaled_a, _ = service.scale_ingredients(recipe_a, recipe_servings=2, people_count=2)
    scaled_b, _ = service.scale_ingredients(recipe_b, recipe_servings=4, people_count=2)

    consolidated, uncertain = service.consolidate([scaled_a, scaled_b])

    tomato = next(item for item in consolidated if item.normalized_name == "tomate")
    assert tomato.required_quantity == 4
    assert tomato.unit == "piece"
    assert uncertain == []


def test_different_units_are_not_merged():
    service = IngredientService()

    group_a = [
        ParsedIngredient(name="basilic", quantity=1, unit="botte", raw_text="1 botte de basilic"),
    ]
    group_b = [
        ParsedIngredient(name="basilic", quantity=20, unit="g", raw_text="20 g de basilic"),
    ]

    consolidated, _ = service.consolidate([group_a, group_b])
    assert len(consolidated) == 2


def test_null_quantity_goes_to_uncertain():
    service = IngredientService()

    ingredients = [
        ParsedIngredient(
            name="basilic",
            quantity=None,
            unit=None,
            raw_text="une poignée de basilic",
        )
    ]

    _, uncertain = service.consolidate([ingredients])
    assert len(uncertain) == 1
    assert uncertain[0].reason == "quantity_not_detected"
