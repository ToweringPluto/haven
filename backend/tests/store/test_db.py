"""The optional Postgres (Tiger Cloud) connection: URL handling and 'not configured'."""

import pytest
from pydantic import SecretStr

from haven.config import ENV_FILE, Settings
from haven.store import db


def test_tests_never_read_the_local_env_file() -> None:
    assert not ENV_FILE.is_file() or str(ENV_FILE) in {"nul", "/dev/null"}


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "postgres://u:p@h:5432/tsdb?sslmode=require",
            "postgresql+psycopg://u:p@h:5432/tsdb?sslmode=require",
        ),
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_sqlalchemy_url_uses_psycopg(url: str, expected: str) -> None:
    assert db.sqlalchemy_url(url) == expected


def test_no_database_configured_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HAVEN_DATABASE_URL", raising=False)
    db.get_engine.cache_clear()
    with pytest.raises(db.DatabaseNotConfiguredError, match="HAVEN_DATABASE_URL"):
        db.get_engine()
    db.get_engine.cache_clear()


def test_database_url_is_kept_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAVEN_DATABASE_URL", "postgres://u:hunter2@h/db")
    settings = Settings()
    assert isinstance(settings.database_url, SecretStr)
    assert "hunter2" not in repr(settings)
