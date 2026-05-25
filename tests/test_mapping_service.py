import pytest
from fastapi import HTTPException

from app.schemas.mapping import ProductMappingCreate
from app.services.mapping_service import MappingService


def test_create_and_list_mapping(db_session):
    service = MappingService(db_session)

    created = service.create_mapping(
        ProductMappingCreate(
            normalized_ingredient_name="Tomates",
            monmarche_product_name="Tomates rondes",
            monmarche_product_url="https://www.mon-marche.fr/tomates",
            search_query="tomate",
            package_quantity=1,
            package_unit="piece",
            confidence_score=1.0,
        )
    )

    assert created.normalized_ingredient_name == "tomate"
    mappings = service.list_mappings()
    assert len(mappings) == 1
    assert mappings[0].monmarche_product_name == "Tomates rondes"


def test_duplicate_mapping_raises_conflict(db_session):
    service = MappingService(db_session)
    payload = ProductMappingCreate(
        normalized_ingredient_name="tomate",
        monmarche_product_name="Tomates rondes",
        monmarche_product_url="https://www.mon-marche.fr/tomates",
        search_query="tomate",
    )

    service.create_mapping(payload)

    with pytest.raises(HTTPException) as exc:
        service.create_mapping(payload)

    assert exc.value.status_code == 409


def test_resolve_products_with_package_quantity(db_session):
    service = MappingService(db_session)
    service.create_mapping(
        ProductMappingCreate(
            normalized_ingredient_name="spaghetti",
            monmarche_product_name="Spaghetti 500g",
            monmarche_product_url="https://www.mon-marche.fr/spaghetti",
            search_query="spaghetti",
            package_quantity=500,
            package_unit="g",
        )
    )

    class Ingredient:
        def __init__(self):
            self.name = "spaghetti"
            self.normalized_name = "spaghetti"
            self.required_quantity = 300
            self.unit = "g"
            self.optional = False

    products, missing = service.resolve_products([Ingredient()])
    assert missing == []
    assert products[0].quantity_to_add == 1
