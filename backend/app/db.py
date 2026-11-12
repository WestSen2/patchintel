"""Database engine/session setup.

SQLite by default (check_same_thread off for FastAPI's threadpool);
Postgres when DATABASE_URL points at the docker-compose service.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables. Alembic replaces this once the schema stabilizes (M2)."""
    from . import models  # noqa: F401  (register models before create_all)

    Base.metadata.create_all(bind=engine)
