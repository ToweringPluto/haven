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


CONNECT_TIMEOUT_S = 5
"""Seconds to wait for Postgres to answer before giving up (libpq applies it per address).

Without it, a database the network silently drops (e.g. a firewall blocking Tiger Cloud's
port) makes the first connection, and so API startup, hang instead of failing."""


def engine_for(url: str) -> Engine:
    """An engine for ``url`` that fails fast when Postgres can't be reached.

    A ``connect_timeout`` already in the URL is respected; non-Postgres URLs (SQLite in tests)
    get no extra arguments.
    """
    url = sqlalchemy_url(url)
    connect_args: dict[str, int] = {}
    if url.startswith("postgresql") and "connect_timeout=" not in url:
        connect_args["connect_timeout"] = CONNECT_TIMEOUT_S
    return create_engine(
        url,
        pool_pre_ping=True,  # Tiger Cloud services can idle out connections
        connect_args=connect_args,
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """The process-wide engine. Raises if no database is configured."""
    settings = Settings()
    if settings.database_url is None:
        raise DatabaseNotConfiguredError("Set HAVEN_DATABASE_URL (see backend/.env.example).")
    return engine_for(settings.database_url.get_secret_value())


def ping() -> str:
    """Run a trivial query and return the server version string."""
    with get_engine().connect() as conn:
        return str(conn.execute(text("select version()")).scalar_one())
