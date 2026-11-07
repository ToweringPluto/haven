"""The committed contract is current, deterministic, valid, and its examples match its schemas."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from openapi_spec_validator import validate

from scripts import export_openapi
from scripts.export_openapi import SPEC_PATH, build_spec, example_errors, render

CHANGELOG = SPEC_PATH.parent / "CHANGELOG.md"


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    return build_spec()


def test_committed_spec_is_current(spec: dict[str, Any]) -> None:
    assert SPEC_PATH.read_text(encoding="utf-8") == render(spec), "run `poe export-openapi`"


def test_render_is_deterministic(spec: dict[str, Any]) -> None:
    assert render(spec) == render(build_spec())
    assert render(spec) == render(yaml.safe_load(render(spec)))


def test_version_and_changelog(spec: dict[str, Any]) -> None:
    version = spec["info"]["version"]
    assert version == "0.1.2"
    assert f"## {version}" in CHANGELOG.read_text(encoding="utf-8")


def test_spec_is_valid_openapi(spec: dict[str, Any]) -> None:
    validate(spec)


def test_examples_validate_against_schemas(spec: dict[str, Any]) -> None:
    assert example_errors(spec) == []


def test_example_nulls_survive_export(spec: dict[str, Any]) -> None:
    """FastAPI strips None from the spec; insufficient evidence must keep ``value: null``."""
    op = spec["paths"]["/v1/reports/{report_id}"]["get"]
    report = op["responses"]["200"]["content"]["application/json"]["examples"]["student"]
    band = report["value"]["property"]["council_tax_band"]
    assert band["status"] == "insufficient" and "value" in band and band["value"] is None


def test_example_errors_detects_bad_example(spec: dict[str, Any]) -> None:
    op = spec["paths"]["/v1/reports/{report_id}"]["get"]
    examples = op["responses"]["200"]["content"]["application/json"]["examples"]
    del examples["student"]["value"]["property"]["council_tax_band"]["value"]
    try:
        assert any("student" in e for e in example_errors(spec))
    finally:
        examples["student"]["value"]["property"]["council_tax_band"]["value"] = None


def test_check_fails_on_stale_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stale = tmp_path / "openapi.yaml"
    stale.write_text(SPEC_PATH.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
    monkeypatch.setattr(export_openapi, "SPEC_PATH", stale)
    assert export_openapi.check() == 1
    monkeypatch.setattr(export_openapi, "SPEC_PATH", tmp_path / "missing.yaml")
    assert export_openapi.check() == 1


def test_check_passes_on_committed_file() -> None:
    assert export_openapi.check() == 0
