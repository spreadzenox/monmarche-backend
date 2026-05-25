import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("API_AUTH_TOKEN", "dev-token")

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal, init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    init_db()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer dev-token"}


@pytest.fixture
def db_session():
    from app.db.models import Order, OrderItem, ProductMapping

    db = SessionLocal()
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(ProductMapping).delete()
    db.commit()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
