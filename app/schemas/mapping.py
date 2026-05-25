"""Product mapping schemas."""

from pydantic import BaseModel, Field


class ProductMappingBase(BaseModel):
    normalized_ingredient_name: str
    monmarche_product_name: str
    monmarche_product_url: str
    search_query: str
    package_quantity: float | None = None
    package_unit: str | None = None
    confidence_score: float = 1.0


class ProductMappingCreate(ProductMappingBase):
    pass


class ProductMappingUpdate(BaseModel):
    normalized_ingredient_name: str | None = None
    monmarche_product_name: str | None = None
    monmarche_product_url: str | None = None
    search_query: str | None = None
    package_quantity: float | None = None
    package_unit: str | None = None
    confidence_score: float | None = None


class ProductMappingResponse(ProductMappingBase):
    id: str

    model_config = {"from_attributes": True}


class MissingMapping(BaseModel):
    ingredient: str
    normalized_name: str
    suggested_search_query: str


class MappedProduct(BaseModel):
    ingredient: str
    product_name: str
    product_url: str
    quantity_to_add: int
    confidence_score: float
    status: str = "mapped"
