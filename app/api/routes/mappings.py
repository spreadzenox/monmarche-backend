"""Product mapping endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.security import require_session
from app.schemas.mapping import (
    ProductMappingCreate,
    ProductMappingResponse,
    ProductMappingUpdate,
)
from app.services.mapping_service import MappingService

router = APIRouter(prefix="/mappings", tags=["mappings"], dependencies=[Depends(require_session)])


@router.get("", response_model=list[ProductMappingResponse])
def list_mappings(db: Session = Depends(get_db)) -> list[ProductMappingResponse]:
    return MappingService(db).list_mappings()


@router.post("", response_model=ProductMappingResponse, status_code=201)
def create_mapping(
    payload: ProductMappingCreate,
    db: Session = Depends(get_db),
) -> ProductMappingResponse:
    return MappingService(db).create_mapping(payload)


@router.patch("/{mapping_id}", response_model=ProductMappingResponse)
def update_mapping(
    mapping_id: str,
    payload: ProductMappingUpdate,
    db: Session = Depends(get_db),
) -> ProductMappingResponse:
    return MappingService(db).update_mapping(mapping_id, payload)


@router.delete("/{mapping_id}", status_code=204)
def delete_mapping(mapping_id: str, db: Session = Depends(get_db)) -> None:
    MappingService(db).delete_mapping(mapping_id)
