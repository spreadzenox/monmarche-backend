import os
import subprocess
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["NOTION_TOKEN"] = ""
os.environ["NOTION_RECIPES_DATABASE_ID"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["APP_ENV"] = "dev"

TEST_HTPASSWD = Path("/tmp/monmarche-test.htpasswd")
subprocess.run(
    ["htpasswd", "-bc", str(TEST_HTPASSWD), "testuser", "testpass"],
    check=True,
    capture_output=True,
)
os.environ["AUTH_HTPASSWD_PATH"] = str(TEST_HTPASSWD)

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import SessionLocal, init_db
from app.main import app

get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    init_db()
    yield
    TEST_HTPASSWD.unlink(missing_ok=True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(client, db_session):
    response = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def db_session():
    from app.db.models import CachedRecipe, Order, OrderItem, ProductMapping, UserSession

    db = SessionLocal()
    db.query(UserSession).delete()
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(ProductMapping).delete()
    db.query(CachedRecipe).delete()
    db.commit()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
