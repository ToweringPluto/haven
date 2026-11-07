from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ConfigDict

from haven.reference import (
    ReferenceDataError,
    ReferenceDocument,
    iter_reference_files,
    load_all_references,
    load_reference,
    load_reference_file,
)

GOOD_META = """\
meta:
  source_url: https://example.org/data.csv
  retrieved: 2026-01-15
  licence: OGL v3.0
  notes: Synthetic test file.
"""


class Rates(ReferenceDocument):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rates: dict[str, float]


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_load_typed(tmp_path: Path) -> None:
    write(tmp_path, "rates.yaml", GOOD_META + "rates:\n  a: 1.5\n  b: 2\n")
    doc = load_reference("rates", Rates, directory=tmp_path)
    assert doc.rates == {"a": 1.5, "b": 2.0}
    assert doc.meta.retrieved == date(2026, 1, 15)
    assert doc.meta.licence == "OGL v3.0"
    assert load_reference("rates.yaml", Rates, directory=tmp_path) == doc


def test_typed_model_rejects_unknown_keys(tmp_path: Path) -> None:
    path = write(tmp_path, "rates.yaml", GOOD_META + "rates: {a: 1}\nextra: 1\n")
    with pytest.raises(ReferenceDataError, match="rates.yaml"):
        load_reference_file(path, Rates)


def test_typed_model_rejects_wrong_types(tmp_path: Path) -> None:
    path = write(tmp_path, "rates.yaml", GOOD_META + "rates: {a: lots}\n")
    with pytest.raises(ReferenceDataError):
        load_reference_file(path, Rates)


def test_generic_document_keeps_data(tmp_path: Path) -> None:
    write(tmp_path, "x.yaml", GOOD_META + "anything: [1, 2]\n")
    docs = load_all_references(tmp_path)
    assert list(docs) == ["x"]
    assert docs["x"].model_extra == {"anything": [1, 2]}


@pytest.mark.parametrize("field", ["source_url", "retrieved", "licence", "notes"])
def test_missing_meta_field_fails(tmp_path: Path, field: str) -> None:
    lines = [ln for ln in GOOD_META.splitlines() if not ln.strip().startswith(f"{field}:")]
    path = write(tmp_path, "x.yaml", "\n".join(lines) + "\n")
    with pytest.raises(ReferenceDataError, match=field):
        load_reference_file(path, ReferenceDocument)


@pytest.mark.parametrize("field", ["licence", "notes"])
def test_empty_meta_field_fails(tmp_path: Path, field: str) -> None:
    text = GOOD_META.replace(f"{field}: ", f'{field}: ""  # ')
    path = write(tmp_path, "x.yaml", text)
    with pytest.raises(ReferenceDataError, match=field):
        load_reference_file(path, ReferenceDocument)


def test_missing_meta_block_fails(tmp_path: Path) -> None:
    path = write(tmp_path, "x.yaml", "rates: {a: 1}\n")
    with pytest.raises(ReferenceDataError, match="meta"):
        load_reference_file(path, ReferenceDocument)


def test_future_retrieved_date_fails(tmp_path: Path) -> None:
    tomorrow = date.today() + timedelta(days=1)
    path = write(tmp_path, "x.yaml", GOOD_META.replace("2026-01-15", tomorrow.isoformat()))
    with pytest.raises(ReferenceDataError, match="future"):
        load_reference_file(path, ReferenceDocument)


def test_today_retrieved_date_ok(tmp_path: Path) -> None:
    path = write(tmp_path, "x.yaml", GOOD_META.replace("2026-01-15", date.today().isoformat()))
    assert load_reference_file(path, ReferenceDocument).meta.retrieved == date.today()


def test_non_http_source_url_fails(tmp_path: Path) -> None:
    path = write(tmp_path, "x.yaml", GOOD_META.replace("https://example.org/data.csv", "n/a"))
    with pytest.raises(ReferenceDataError, match="source_url"):
        load_reference_file(path, ReferenceDocument)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ReferenceDataError, match="not found"):
        load_reference("nope", ReferenceDocument, directory=tmp_path)


def test_invalid_yaml(tmp_path: Path) -> None:
    path = write(tmp_path, "x.yaml", "meta: [unclosed\n")
    with pytest.raises(ReferenceDataError, match="invalid YAML"):
        load_reference_file(path, ReferenceDocument)


@pytest.mark.parametrize("text", ["", "- a\n- b\n", "just a string\n"])
def test_non_mapping_top_level(tmp_path: Path, text: str) -> None:
    path = write(tmp_path, "x.yaml", text)
    with pytest.raises(ReferenceDataError, match="mapping"):
        load_reference_file(path, ReferenceDocument)


def test_iter_sorted_and_yaml_only(tmp_path: Path) -> None:
    for name in ["b.yaml", "a.yaml", "c.yml", "README.md"]:
        write(tmp_path, name, GOOD_META)
    assert [p.name for p in iter_reference_files(tmp_path)] == ["a.yaml", "b.yaml"]


def test_iter_missing_directory(tmp_path: Path) -> None:
    assert list(iter_reference_files(tmp_path / "absent")) == []


def test_documents_are_frozen(tmp_path: Path) -> None:
    write(tmp_path, "rates.yaml", GOOD_META + "rates: {a: 1}\n")
    doc = load_reference("rates", Rates, directory=tmp_path)
    with pytest.raises(ValueError):
        doc.rates = {}
