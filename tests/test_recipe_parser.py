from app.services.recipe_parser_service import RecipeParserService


def test_parse_ingredients_section():
    content = """
# Poulet rôti

Pour 4 personnes

## Ingrédients
200 g de riz
2 tomates
- 3 c. à soupe d'huile d'olive
• 100 g de feta
1/2 citron
0,5 concombre
une belle poignée de basilic

## Préparation
Faire cuire le riz.
"""
    parsed = RecipeParserService().parse(content)

    assert parsed.servings == 4
    assert len(parsed.ingredients) >= 6
    assert parsed.ingredients[0].name == "riz"
    assert parsed.ingredients[0].quantity == 200
    assert parsed.ingredients[0].unit == "g"

    tomato = next(item for item in parsed.ingredients if "tomate" in item.name)
    assert tomato.quantity == 2
    assert tomato.unit == "piece"

    feta = next(item for item in parsed.ingredients if "feta" in item.name)
    assert feta.quantity == 100
    assert feta.unit == "g"

    citron = next(item for item in parsed.ingredients if "citron" in item.name)
    assert citron.quantity == 0.5

    assert any("Faire cuire" in step for step in parsed.instructions)


def test_parse_uncertain_quantity():
    content = """
## Ingrédients
une belle poignée de basilic
"""
    parsed = RecipeParserService().parse(content)
    basilic = parsed.ingredients[0]
    assert basilic.quantity is None
    assert basilic.unit is None


def test_default_servings():
    content = """
## Ingrédients
1 oignon
"""
    parsed = RecipeParserService().parse(content)
    assert parsed.servings == 2
