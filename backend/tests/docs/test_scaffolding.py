"""P0-08 scaffolding: data-source inventory, datasheet template, ml project, Docker files."""

import re
import tomllib
from typing import Any

import pytest
import yaml

from haven.config import REPO_ROOT

DATA_SOURCES = REPO_ROOT / "docs" / "DATA_SOURCES.md"
TEMPLATE = REPO_ROOT / "docs" / "datasets" / "_TEMPLATE.md"
COMPOSE = REPO_ROOT / "docker-compose.yml"
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
ML_PYPROJECT = REPO_ROOT / "ml" / "pyproject.toml"

INVENTORY_COLUMNS = ["Need", "Source", "URL", "Licence", "Retrieval status", "Known gaps"]
STATUS_RE = re.compile(
    r"^(not retrieved|not generated|not collected|blocked|retrieved \d{4}-\d{2}-\d{2})\b"
)


def _inventory_rows() -> list[dict[str, str]]:
    text = DATA_SOURCES.read_text(encoding="utf-8")
    section = text.split("## Inventory", 1)[1].split("\n## ", 1)[0]
    lines = [ln.strip() for ln in section.splitlines() if ln.strip().startswith("|")]
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    assert header == INVENTORY_COLUMNS
    return [
        dict(zip(header, (c.strip() for c in ln.strip("|").split("|")), strict=True))
        for ln in lines[2:]
    ]


def test_data_sources_inventory_rows_are_complete() -> None:
    rows = _inventory_rows()
    assert len(rows) >= 10
    for row in rows:
        for col in INVENTORY_COLUMNS:
            assert row[col], f"empty {col!r} in row {row['Need']!r}"
        assert (
            row["URL"].startswith("https://")
            or row["URL"] == "(generated locally)"
            or (row["URL"].startswith("(collected"))
        ), row
        assert STATUS_RE.match(row["Retrieval status"]), row["Retrieval status"]


@pytest.mark.parametrize(
    "url",
    [
        # Later tasks read these from the inventory (P1-02, P1-03, P1-04, P2-02, P2-04).
        "https://www.edinburgh.gov.uk/downloads/file/36923/council-tax-charges-2025",
        "https://www.edinburgh.gov.uk/downloads/file/39463/council-tax-charges-2026",
        "https://data.gov.scot/dataset/domestic_energy_performance_certificates___dataset_to_q1_2026",
        "https://www.gov.scot/publications/private-sector-rent-statistics-scotland-2010-to-2025/",
        "https://www.opendata.nhs.scot/dataset/gp-practice-contact-details-and-list-sizes",
        "https://zenodo.org/records/6554286",
    ],
)
def test_data_sources_lists_planned_sources(url: str) -> None:
    assert any(row["URL"] == url for row in _inventory_rows()), url


def test_data_sources_has_retrieved_files_section() -> None:
    text = DATA_SOURCES.read_text(encoding="utf-8")
    assert "## Retrieved files" in text
    assert "sha256" in text


@pytest.mark.parametrize(
    "heading",
    [
        "Purpose",
        "Composition",
        "Sourcing and consent",
        "Licence",
        "Labelling",
        "Splits",
        "Known biases and limitations",
        "Maintenance",
    ],
)
def test_datasheet_template_has_sections(heading: str) -> None:
    assert f"\n## {heading}\n" in TEMPLATE.read_text(encoding="utf-8")


def test_datasheet_template_links_labelling_guide() -> None:
    assert "ml/guidelines/" in TEMPLATE.read_text(encoding="utf-8")


def test_ml_project_declares_base_deps() -> None:
    data = tomllib.loads(ML_PYPROJECT.read_text(encoding="utf-8"))
    deps = {
        re.split(r"[<>=!~ ;\[]", d, maxsplit=1)[0].lower() for d in data["project"]["dependencies"]
    }
    assert {"numpy", "pillow", "scikit-learn"} <= deps
    assert (REPO_ROOT / "ml" / "README.md").is_file()
    assert (REPO_ROOT / "ml" / ".python-version").read_text().strip() == "3.12"


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return data


def test_compose_profiles(compose: dict[str, Any]) -> None:
    services = compose["services"]
    assert services["api"]["profiles"] == ["app"]
    assert services["api"]["build"]["context"] == "./backend"
    assert services["openrouteservice"]["profiles"] == ["tools"]
    assert services["label-studio"]["profiles"] == ["tools"]


def test_compose_images_are_pinned(compose: dict[str, Any]) -> None:
    for name, svc in compose["services"].items():
        image = svc.get("image")
        if image is None or "build" in svc:
            continue
        tag = image.rsplit(":", 1)[1] if ":" in image else ""
        assert tag and tag != "latest", f"{name} image {image!r} isn't pinned to a release tag"


def test_dockerfile_uses_uv_and_slim_base() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.12-slim", text, re.M)
    assert re.search(r"COPY --from=astral/uv:\d+\.\d+\.\d+ ", text)
    assert "uv sync --locked --no-dev" in text
    assert "/healthz" in text
