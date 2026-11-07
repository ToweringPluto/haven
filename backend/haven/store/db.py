"""Postgres connection (Tiger Cloud / TimescaleDB) configured from ``HAVEN_DATABASE_URL``."""

from functools import lru_cache

from sqlalchemy import Engine, text
from sqlmodel import create_engine

from haven.config import Settings


class DatabaseNotConfiguredError(RuntimeError):
    """``HAVEN_DATABASE_URL`` isn't set."""


def sqlalchemy_url(url: str) -> str:
    """Point a plain ``postgres://`` URL (as Tiger Cloud gives it) at the psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """The process-wide engine. Raises if no database is configured."""
    settings = Settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError("Set HAVEN_DATABASE_URL (see backend/.env.example).")
    return create_engine(
        sqlalchemy_url(settings.database_url.get_secret_value()),
        pool_pre_ping=True,  # Tiger Cloud services can idle out connections
    )


def ping() -> str:
    """Run a trivial query and return the server version string."""
    with get_engine().connect() as conn:
        return str(conn.execute(text("select version()")).scalar_one())
