"""Every contract example validates against its pydantic model and is marked illustrative."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from haven.api.schemas import ProblemDetail
from haven.domain import Report
from scripts.make_examples import ENDPOINT_MODELS, EXAMPLES_DIR, PERSONAS, SOURCE, build_examples

ERROR_FILES = {"not_found": 404, "validation_error": 422}


def all_example_files() -> list[Path]:
    return sorted(EXAMPLES_DIR.rglob("*.json"))


def model_for(path: Path) -> type[BaseModel]:
    rel = path.relative_to(EXAMPLES_DIR)
    if rel.parent.name == "errors":
        return ProblemDetail
    assert rel.parent.name in PERSONAS, f"unexpected example folder: {rel}"
    return ENDPOINT_MODELS[path.stem]


def sources(node: Any) -> list[str]:
    """Every value under a 'source' key, anywhere in the document."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "source" and isinstance(value, str):
                found.append(value)
            found.extend(sources(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(sources(value))
    return found


def test_expected_files_exist() -> None:
    present = {p.relative_to(EXAMPLES_DIR).as_posix() for p in all_example_files()}
    expected = {f"{p}/{e}.json" for p in PERSONAS for e in ENDPOINT_MODELS}
    expected |= {f"errors/{name}.json" for name in ERROR_FILES}
    assert present == expected


@pytest.mark.parametrize(
    "path", all_example_files(), ids=lambda p: p.relative_to(EXAMPLES_DIR).as_posix()
)
def test_example_validates(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    model_for(path).model_validate(data)


@pytest.mark.parametrize("persona", PERSONAS)
def test_persona_values_are_marked_illustrative(persona: str) -> None:
    for path in (EXAMPLES_DIR / persona).glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        found = sources(data)
        if path.stem == "profile":
            # Profile values are plain user statements (no Evidence); the label marks them.
            assert "illustrative" in data["label"].lower()
            continue
        assert found, f"{path.name} has no sourced values"
        assert set(found) == {SOURCE}, f"{path.name}: {set(found)}"


@pytest.mark.parametrize("persona", PERSONAS)
def test_report_is_illustrative_and_cites_known_ids(persona: str) -> None:
    report = Report.model_validate_json((EXAMPLES_DIR / persona / "report.json").read_text("utf-8"))
    assert report.illustrative and report.property.illustrative
    known = {f.id for f in report.findings} | {s.id for s in report.signals}
    cited = {c for section in report.sections for s in section.sentences for c in s.cites}
    assert cited <= known


@pytest.mark.parametrize("name,status", ERROR_FILES.items())
def test_errors_are_problem_details(name: str, status: int) -> None:
    problem = ProblemDetail.model_validate_json(
        (EXAMPLES_DIR / "errors" / f"{name}.json").read_text("utf-8")
    )
    assert problem.status == status


def test_examples_match_generator() -> None:
    """The committed files are exactly what scripts/make_examples.py produces."""
    for rel, text in build_examples().items():
        assert (EXAMPLES_DIR / rel).read_text(encoding="utf-8") == text, f"stale: {rel}"
