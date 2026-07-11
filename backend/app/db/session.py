from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


engine: Engine | None = None
"""Lazily initialized SQLAlchemy engine shared by backend database sessions."""

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
)
"""Factory for creating SQLAlchemy sessions once the engine is configured."""


def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine without opening a database connection."""

    global engine
    if engine is None:
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        SessionLocal.configure(bind=engine)
    return engine


def ensure_database_schema() -> None:
    """Apply additive schema changes during application startup."""

    from app.db.schema_migrations import ensure_runtime_schema

    ensure_runtime_schema(get_engine())


def get_db() -> Iterator[Session]:
    """Yield a database session for FastAPI dependencies."""

    get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Return whether the backend can execute a simple database query."""

    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
