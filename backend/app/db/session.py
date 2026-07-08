from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine: Engine | None = None
"""Lazily initialized SQLAlchemy engine shared by backend database sessions."""

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
)
"""Factory for creating SQLAlchemy sessions once the engine is configured."""


def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine, creating it on first access."""

    global engine
    if engine is None:
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        SessionLocal.configure(bind=engine)
    return engine


def check_database_connection() -> bool:
    """Return whether the backend can execute a simple database query."""

    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
