"""`poe dev` starts the backend and the frontend together."""

import sys

import pytest

from scripts import dev


def test_backend_command_runs_the_app_factory_on_8000() -> None:
    cmd = dev.backend_command()
    assert cmd[:3] == [sys.executable, "-m", "uvicorn"]
    assert "haven.api.app:create_app" in cmd and "--factory" in cmd
    assert cmd[-2:] == ["--port", "8000"]


def test_frontend_command_uses_the_vite_dev_script() -> None:
    assert dev.frontend_command("npm") == ["npm", "run", "dev"]


def test_paths_point_at_the_repo() -> None:
    assert (dev.FRONTEND_DIR / "package.json").is_file()
    assert (dev.BACKEND_DIR / "pyproject.toml").is_file()


def test_missing_npm_fails_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dev, "find_npm", lambda: None)
    assert dev.main() == 1
