"""Simple database repositories."""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import CachedRecipe, Order, OrderItem, ProductMapping


class ProductMappingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[ProductMapping]:
        return self.db.query(ProductMapping).order_by(ProductMapping.normalized_ingredient_name).all()

    def get_by_id(self, mapping_id: str) -> ProductMapping | None:
        return self.db.query(ProductMapping).filter(ProductMapping.id == mapping_id).first()

    def get_by_normalized_name(self, normalized_name: str) -> ProductMapping | None:
        return (
            self.db.query(ProductMapping)
            .filter(ProductMapping.normalized_ingredient_name == normalized_name)
            .first()
        )

    def create(self, data: dict[str, Any]) -> ProductMapping:
        mapping = ProductMapping(**data)
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def update(self, mapping: ProductMapping, data: dict[str, Any]) -> ProductMapping:
        for key, value in data.items():
            if value is not None:
                setattr(mapping, key, value)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def delete(self, mapping: ProductMapping) -> None:
        self.db.delete(mapping)
        self.db.commit()


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, order_id: str) -> Order | None:
        return self.db.query(Order).filter(Order.id == order_id).first()

    def create(
        self,
        *,
        status: str,
        people_count: int,
        desired_delivery_date: date,
        cart_url: str | None = None,
        checkout_url: str | None = None,
        error_message: str | None = None,
    ) -> Order:
        order = Order(
            status=status,
            people_count=people_count,
            desired_delivery_date=desired_delivery_date,
            cart_url=cart_url,
            checkout_url=checkout_url,
            error_message=error_message,
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order

    def update(self, order: Order, data: dict[str, Any]) -> Order:
        for key, value in data.items():
            if value is not None:
                setattr(order, key, value)
        self.db.commit()
        self.db.refresh(order)
        return order

    def add_items(self, items: list[OrderItem]) -> None:
        self.db.add_all(items)
        self.db.commit()


class OrderItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_order_id(self, order_id: str) -> list[OrderItem]:
        return self.db.query(OrderItem).filter(OrderItem.order_id == order_id).all()


class CachedRecipeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[CachedRecipe]:
        return self.db.query(CachedRecipe).order_by(CachedRecipe.name).all()

    def get_by_id(self, notion_page_id: str) -> CachedRecipe | None:
        page_id = notion_page_id.replace("-", "")
        return self.db.query(CachedRecipe).filter(CachedRecipe.notion_page_id == page_id).first()

    def count(self) -> int:
        return self.db.query(CachedRecipe).count()

    def latest_synced_at(self):
        from sqlalchemy import func

        return self.db.query(func.max(CachedRecipe.synced_at)).scalar()

    def replace_all(self, recipes: list[CachedRecipe]) -> None:
        self.db.query(CachedRecipe).delete()
        self.db.add_all(recipes)
        self.db.commit()
