"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, mappings, monmarche_auth, orders, recipes
from app.core.logging import setup_logging
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    init_db()
    yield


app = FastAPI(
    title="Mon Marché Meal Planner API",
    description="Backend for recipe selection, ingredient consolidation, and cart preparation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(recipes.router)
app.include_router(mappings.router)
app.include_router(orders.router)
app.include_router(monmarche_auth.router)
