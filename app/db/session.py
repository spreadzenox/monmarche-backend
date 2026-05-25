"""SQLAlchemy database session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_kwargs: dict = {"connect_args": connect_args}
if settings.database_url.startswith("sqlite:///:memory:"):
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
