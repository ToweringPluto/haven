"""docs/FRONTEND_INTEGRATION.md exists, covers every /v1 path in the exported contract, and
states the UI obligations."""

from typing import Any

import pytest
import yaml

from haven import __version__
from haven.config import REPO_ROOT

GUIDE = REPO_ROOT / "docs" / "FRONTEND_INTEGRATION.md"
SPEC = REPO_ROOT / "contracts" / "openapi.yaml"


@pytest.fixture(scope="module")
def guide() -> str:
    assert GUIDE.is_file(), f"missing {GUIDE}"
    return GUIDE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    return data


def test_guide_mentions_every_v1_path(guide: str, spec: dict[str, Any]) -> None:
    v1_paths = [p for p in spec["paths"] if p.startswith("/v1")]
    assert v1_paths, "the exported spec has no /v1 paths"
    missing = [p for p in v1_paths if p not in guide]
    assert not missing, f"FRONTEND_INTEGRATION.md doesn't mention: {missing}"


def test_guide_mentions_every_v1_operation(guide: str, spec: dict[str, Any]) -> None:
    methods = {"get", "post", "put", "patch", "delete"}
    missing = [
        f"{m.upper()} {p}"
        for p, ops in spec["paths"].items()
        if p.startswith("/v1")
        for m in ops
        if m in methods and f"{m.upper()} {p}" not in guide
    ]
    assert not missing, f"FRONTEND_INTEGRATION.md doesn't name these operations: {missing}"


def test_guide_states_current_contract_version(guide: str) -> None:
    assert spec_version() == __version__
    assert f"**{__version__}**" in guide


def spec_version() -> str:
    version: str = yaml.safe_load(SPEC.read_text(encoding="utf-8"))["info"]["version"]
    return version


@pytest.mark.parametrize(
    "phrase",
    [
        "poe serve",
        "poe mock",
        "HAVEN_CORS_ORIGINS",
        "contracts/CHANGELOG.md",
        "UI obligations",
        "origin",
        "`unknown` is not `concern`",
        "Never aggregate into a score",
        "Report.disclaimer",
        "Insufficient evidence",
        "DELETE /v1/uploads/{upload_id}",
        "No colour-only meaning",
        "application/problem+json",
    ],
)
def test_guide_covers_required_topics(guide: str, phrase: str) -> None:
    assert phrase in guide
