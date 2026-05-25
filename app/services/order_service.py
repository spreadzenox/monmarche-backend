"""Order preview and cart preparation orchestration."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import OrderItem
from app.db.repositories import OrderRepository
from app.schemas.ingredient import PreviewIngredient
from app.schemas.order import (
    OrderPreviewRequest,
    OrderPreviewResponse,
    OrderResponse,
    PrepareCartResponse,
)
from app.services.ingredient_service import IngredientService
from app.services.mapping_service import MappingService
from app.services.monmarche_bot import MonMarcheBot, MonMarcheBotError
from app.services.notion_service import NotionService, NotionServiceError
from app.services.recipe_parser_service import RecipeParserService

logger = logging.getLogger(__name__)


class OrderService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._settings = get_settings()
        self._orders = OrderRepository(db)
        self._ingredients = IngredientService()
        self._parser = RecipeParserService()
        self._mapping = MappingService(db)

    def preview_order(self, payload: OrderPreviewRequest) -> OrderPreviewResponse:
        try:
            notion = NotionService()
        except NotionServiceError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

        scaled_groups: list = []
        all_uncertain = []

        for recipe_id in payload.recipe_ids:
            try:
                recipe = notion.get_recipe(recipe_id)
            except NotionServiceError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(exc),
                ) from exc

            parsed = self._parser.parse(recipe.raw_content)
            scaled, uncertain = self._ingredients.scale_ingredients(
                parsed.ingredients,
                recipe_servings=parsed.servings,
                people_count=payload.people_count,
            )
            scaled_groups.append(scaled)
            all_uncertain.extend(uncertain)

        consolidated, consolidate_uncertain = self._ingredients.consolidate(scaled_groups)
        all_uncertain.extend(consolidate_uncertain)

        products, missing_mappings = self._mapping.resolve_products(consolidated)

        if missing_mappings:
            order_status = "missing_mappings"
        else:
            order_status = "ready_to_prepare_cart"

        order = self._orders.create(
            status=order_status,
            people_count=payload.people_count,
            desired_delivery_date=payload.desired_delivery_date,
            cart_url=self._settings.monmarche_cart_url,
        )

        product_by_normalized = {
            self._mapping._normalization.normalize(product.ingredient): product
            for product in products
        }

        order_items: list[OrderItem] = []
        for ingredient in consolidated:
            mapped = product_by_normalized.get(ingredient.normalized_name)
            order_items.append(
                OrderItem(
                    order_id=order.id,
                    ingredient_name=ingredient.name,
                    normalized_ingredient_name=ingredient.normalized_name,
                    required_quantity=ingredient.required_quantity,
                    required_unit=ingredient.unit,
                    product_name=mapped.product_name if mapped else None,
                    product_url=mapped.product_url if mapped else None,
                    quantity_to_add=mapped.quantity_to_add if mapped else None,
                    status="mapped" if mapped else "missing_mapping",
                    raw_text=ingredient.raw_text,
                )
            )

        self._orders.add_items(order_items)

        preview_ingredients = [
            PreviewIngredient(
                name=item.name,
                normalized_name=item.normalized_name,
                required_quantity=item.required_quantity,
                unit=item.unit,
            )
            for item in consolidated
            if item.required_quantity is not None
        ]

        return OrderPreviewResponse(
            order_id=order.id,
            status=order_status,
            ingredients=preview_ingredients,
            products=products,
            missing_mappings=missing_mappings,
            uncertain_ingredients=all_uncertain,
            cart_url=self._settings.monmarche_cart_url,
            checkout_url=None,
        )

    def get_order(self, order_id: str) -> OrderResponse:
        order = self._orders.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return OrderResponse.model_validate(order)

    def get_order_status(self, order_id: str):
        from app.schemas.order import OrderStatusResponse

        order = self._orders.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return OrderStatusResponse(
            order_id=order.id,
            status=order.status,
            cart_url=order.cart_url,
            checkout_url=order.checkout_url,
            error_message=order.error_message,
        )

    def prepare_cart(self, order_id: str) -> PrepareCartResponse:
        order = self._orders.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        missing_items = [item for item in order.items if item.status == "missing_mapping"]
        if missing_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot prepare cart while required product mappings are missing",
            )

        mapped_items = [item for item in order.items if item.status == "mapped" and item.product_url]
        if not mapped_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No mapped products available for cart preparation",
            )

        self._orders.update(order, {"status": "cart_preparation_running", "error_message": None})

        bot = MonMarcheBot()
        products_payload = [
            {
                "ingredient": item.ingredient_name,
                "product_name": item.product_name or item.ingredient_name,
                "product_url": item.product_url,
                "search_query": item.normalized_ingredient_name,
                "quantity_to_add": item.quantity_to_add or 1,
            }
            for item in mapped_items
        ]

        try:
            result = bot.prepare_cart(products_payload)
        except MonMarcheBotError as exc:
            self._orders.update(
                order,
                {
                    "status": "cart_failed",
                    "error_message": str(exc),
                },
            )
            return PrepareCartResponse(
                status="cart_failed",
                failed_products=[],
                cart_url=self._settings.monmarche_cart_url,
                error=str(exc),
            )

        if result.failed_products:
            status_value = "cart_failed" if not result.added_products else "cart_prepared"
            error_message = "Some products could not be added to the cart"
        else:
            status_value = "cart_prepared"
            error_message = None

        self._orders.update(
            order,
            {
                "status": status_value,
                "cart_url": result.cart_url,
                "checkout_url": result.checkout_url,
                "error_message": error_message,
            },
        )

        return PrepareCartResponse(
            status=status_value,
            added_products=result.added_products,
            failed_products=result.failed_products,
            cart_url=result.cart_url,
            checkout_url=result.checkout_url,
            error=error_message,
        )
