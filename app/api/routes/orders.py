"""Order endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.security import verify_api_token
from app.schemas.order import (
    OrderPreviewRequest,
    OrderPreviewResponse,
    OrderResponse,
    OrderStatusResponse,
    PrepareCartResponse,
)
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"], dependencies=[Depends(verify_api_token)])


@router.post("/preview", response_model=OrderPreviewResponse)
def preview_order(
    payload: OrderPreviewRequest,
    db: Session = Depends(get_db),
) -> OrderPreviewResponse:
    return OrderService(db).preview_order(payload)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, db: Session = Depends(get_db)) -> OrderResponse:
    return OrderService(db).get_order(order_id)


@router.get("/{order_id}/status", response_model=OrderStatusResponse)
def get_order_status(order_id: str, db: Session = Depends(get_db)) -> OrderStatusResponse:
    return OrderService(db).get_order_status(order_id)


@router.post("/{order_id}/prepare-cart", response_model=PrepareCartResponse)
def prepare_cart(order_id: str, db: Session = Depends(get_db)) -> PrepareCartResponse:
    return OrderService(db).prepare_cart(order_id)
