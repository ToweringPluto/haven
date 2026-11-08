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


def _captured_connect_args(monkeypatch: pytest.MonkeyPatch, url: str) -> dict[str, object]:
    seen: dict[str, object] = {}

    def fake_create_engine(url: str, **kwargs: object) -> object:
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(db, "create_engine", fake_create_engine)
    db.engine_for(url)
    args = seen["connect_args"]
    assert isinstance(args, dict)
    return args


def test_postgres_engines_get_a_connect_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    args = _captured_connect_args(monkeypatch, "postgres://u:p@h:5432/db?sslmode=require")
    assert args == {"connect_timeout": db.CONNECT_TIMEOUT_S}


def test_a_timeout_in_the_url_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _captured_connect_args(monkeypatch, "postgresql://u:p@h/db?connect_timeout=30") == {}


def test_sqlite_engines_get_no_postgres_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _captured_connect_args(monkeypatch, "sqlite://") == {}
