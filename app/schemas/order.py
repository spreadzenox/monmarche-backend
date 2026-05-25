"""Order schemas."""

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.ingredient import PreviewIngredient, UncertainIngredient
from app.schemas.mapping import MappedProduct, MissingMapping


class OrderPreviewRequest(BaseModel):
    recipe_ids: list[str] = Field(min_length=1)
    people_count: int = Field(ge=1)
    desired_delivery_date: date


class OrderPreviewResponse(BaseModel):
    order_id: str
    status: str
    ingredients: list[PreviewIngredient]
    products: list[MappedProduct]
    missing_mappings: list[MissingMapping]
    uncertain_ingredients: list[UncertainIngredient]
    cart_url: str | None = None
    checkout_url: str | None = None


class OrderItemResponse(BaseModel):
    id: str
    ingredient_name: str
    normalized_ingredient_name: str
    required_quantity: float | None = None
    required_unit: str | None = None
    product_name: str | None = None
    product_url: str | None = None
    quantity_to_add: int | None = None
    status: str
    raw_text: str | None = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: str
    status: str
    people_count: int
    desired_delivery_date: date
    cart_url: str | None = None
    checkout_url: str | None = None
    error_message: str | None = None
    items: list[OrderItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class OrderStatusResponse(BaseModel):
    order_id: str
    status: str
    cart_url: str | None = None
    checkout_url: str | None = None
    error_message: str | None = None


class PrepareCartProductResult(BaseModel):
    ingredient: str
    product_name: str
    product_url: str | None = None
    success: bool
    message: str | None = None


class PrepareCartResponse(BaseModel):
    status: str
    added_products: list[PrepareCartProductResult] = Field(default_factory=list)
    failed_products: list[PrepareCartProductResult] = Field(default_factory=list)
    cart_url: str | None = None
    checkout_url: str | None = None
    error: str | None = None
