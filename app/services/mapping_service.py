"""Product mapping CRUD and lookup."""

from __future__ import annotations

import math

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ProductMapping
from app.db.repositories import ProductMappingRepository
from app.schemas.mapping import (
    MappedProduct,
    MissingMapping,
    ProductMappingCreate,
    ProductMappingResponse,
    ProductMappingUpdate,
)
from app.services.normalization_service import NormalizationService


class MappingService:
    def __init__(
        self,
        db: Session,
        normalization_service: NormalizationService | None = None,
    ) -> None:
        self._repo = ProductMappingRepository(db)
        self._normalization = normalization_service or NormalizationService()

    def list_mappings(self) -> list[ProductMappingResponse]:
        return [ProductMappingResponse.model_validate(item) for item in self._repo.list_all()]

    def create_mapping(self, payload: ProductMappingCreate) -> ProductMappingResponse:
        normalized_name = self._normalization.normalize(payload.normalized_ingredient_name)
        data = payload.model_dump()
        data["normalized_ingredient_name"] = normalized_name

        existing = self._repo.get_by_normalized_name(normalized_name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A mapping already exists for ingredient '{normalized_name}'",
            )

        try:
            mapping = self._repo.create(data)
        except IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A mapping already exists for ingredient '{normalized_name}'",
            ) from exc

        return ProductMappingResponse.model_validate(mapping)

    def update_mapping(self, mapping_id: str, payload: ProductMappingUpdate) -> ProductMappingResponse:
        mapping = self._repo.get_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")

        data = payload.model_dump(exclude_unset=True)
        if "normalized_ingredient_name" in data and data["normalized_ingredient_name"] is not None:
            data["normalized_ingredient_name"] = self._normalization.normalize(
                data["normalized_ingredient_name"]
            )
            existing = self._repo.get_by_normalized_name(data["normalized_ingredient_name"])
            if existing and existing.id != mapping.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A mapping already exists for ingredient '{data['normalized_ingredient_name']}'",
                )

        updated = self._repo.update(mapping, data)
        return ProductMappingResponse.model_validate(updated)

    def delete_mapping(self, mapping_id: str) -> None:
        mapping = self._repo.get_by_id(mapping_id)
        if not mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
        self._repo.delete(mapping)

    def resolve_products(
        self,
        consolidated_ingredients: list,
    ) -> tuple[list[MappedProduct], list[MissingMapping]]:
        products: list[MappedProduct] = []
        missing: list[MissingMapping] = []

        for ingredient in consolidated_ingredients:
            if ingredient.optional:
                continue

            mapping = self._repo.get_by_normalized_name(ingredient.normalized_name)
            if not mapping:
                missing.append(
                    MissingMapping(
                        ingredient=ingredient.name,
                        normalized_name=ingredient.normalized_name,
                        suggested_search_query=ingredient.normalized_name,
                    )
                )
                continue

            quantity_to_add = self._compute_packages_to_add(
                required_quantity=ingredient.required_quantity,
                required_unit=ingredient.unit,
                mapping=mapping,
            )
            products.append(
                MappedProduct(
                    ingredient=ingredient.name,
                    product_name=mapping.monmarche_product_name,
                    product_url=mapping.monmarche_product_url,
                    quantity_to_add=quantity_to_add,
                    confidence_score=mapping.confidence_score,
                    status="mapped",
                )
            )

        return products, missing

    @staticmethod
    def _compute_packages_to_add(
        *,
        required_quantity: float | None,
        required_unit: str | None,
        mapping: ProductMapping,
    ) -> int:
        if required_quantity is None:
            return 1

        if (
            mapping.package_quantity
            and mapping.package_unit
            and required_unit
            and mapping.package_unit == required_unit
            and mapping.package_quantity > 0
        ):
            return max(1, math.ceil(required_quantity / mapping.package_quantity))

        return max(1, math.ceil(required_quantity)) if required_quantity >= 1 else 1
