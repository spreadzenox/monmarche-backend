"""SQLAlchemy ORM models."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class ProductMapping(Base):
    __tablename__ = "product_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    normalized_ingredient_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    monmarche_product_name: Mapped[str] = mapped_column(String(512))
    monmarche_product_url: Mapped[str] = mapped_column(String(1024))
    search_query: Mapped[str] = mapped_column(String(255))
    package_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    package_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    status: Mapped[str] = mapped_column(String(64), default="draft", index=True)
    people_count: Mapped[int] = mapped_column(Integer)
    desired_delivery_date: Mapped[date] = mapped_column(Date)
    cart_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), index=True)
    ingredient_name: Mapped[str] = mapped_column(String(255))
    normalized_ingredient_name: Mapped[str] = mapped_column(String(255), index=True)
    required_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    required_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    product_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    quantity_to_add: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="pending")
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["Order"] = relationship("Order", back_populates="items")


class CachedRecipe(Base):
    __tablename__ = "cached_recipes"

    notion_page_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(512), index=True)
    status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rating: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_content: Mapped[str] = mapped_column(Text, default="")
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
