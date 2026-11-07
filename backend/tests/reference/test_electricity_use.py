"""Ofgem TDCV (single-rate electricity) reference data: committed YAML, schema and parser."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from haven.reference import ElectricityUseReference, UsageLevels, load_electricity_use
from scripts import ingest_electricity_tdcv as ingest
from scripts.ingest_electricity_tdcv import (
    CONSULTATION,
    DECISION,
    IngestError,
    check_method,
    parse_decision,
    parse_sources,
    pdf_text,
)
from scripts.ingest_energy_rates import TDCV_KWH


@pytest.fixture(scope="module")
def reference() -> ElectricityUseReference:
    return load_electricity_use()


def test_committed_values(reference: ElectricityUseReference) -> None:
    # Ofgem decision, Table 1, Electricity Profile Class 1, 2026 TDCV column.
    assert reference.electricity == UsageLevels(
        low_kwh_per_year=1600, medium_kwh_per_year=2500, high_kwh_per_year=3800
    )
    assert reference.valid_from == date(2026, 7, 1)
    assert reference.decision_published == date(2026, 5, 27)


def test_scope_is_stated_honestly(reference: ElectricityUseReference) -> None:
    assert reference.lighting_and_appliances_only is False
    assert reference.end_uses == "all_metered_electricity"
    assert reference.geography == "Great Britain"
    assert "double-count" in reference.meta.notes
    assert "not uncertainty for one property" in reference.meta.notes


def test_medium_matches_price_cap_benchmark(reference: ElectricityUseReference) -> None:
    # The Oct-Dec 2026 cap levels PDF quotes bills at the same TDCV (ingest_energy_rates).
    assert reference.electricity.medium_kwh_per_year == TDCV_KWH["electricity"]


def test_provenance_points_at_ofgem(reference: ElectricityUseReference) -> None:
    assert reference.meta.source_url == DECISION.url == reference.source_url
    assert reference.method_source_url == CONSULTATION.url
    assert "Open Government Licence" in reference.meta.licence


def test_in_force(reference: ElectricityUseReference) -> None:
    assert reference.in_force(date(2026, 11, 7))
    assert reference.in_force(date(2026, 7, 1))
    assert not reference.in_force(date(2026, 6, 30))


def test_reparse_raw_pdfs_match_yaml(reference: ElectricityUseReference) -> None:
    if not (DECISION.path.is_file() and CONSULTATION.path.is_file()):
        pytest.skip("raw TDCV PDFs not present (run ingest_electricity_tdcv.py --download)")
    assert parse_sources() == reference.model_dump(mode="python", exclude={"meta"})


def test_check_mode_passes() -> None:
    assert ingest.main(["--check"]) == 0


# --- schema --------------------------------------------------------------------------------


def test_levels_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="low < medium < high"):
        UsageLevels(low_kwh_per_year=2500, medium_kwh_per_year=1600, high_kwh_per_year=3800)


def test_lighting_only_claim_rejected(reference: ElectricityUseReference) -> None:
    data = reference.model_dump(mode="json")
    data["lighting_and_appliances_only"] = True
    with pytest.raises(ValidationError):
        ElectricityUseReference.model_validate(data)


def test_valid_from_not_before_decision(reference: ElectricityUseReference) -> None:
    data = reference.model_dump(mode="json")
    data["valid_from"] = "2026-01-01"
    with pytest.raises(ValidationError, match="decision_published"):
        ElectricityUseReference.model_validate(data)


# --- decision parser on synthetic text -----------------------------------------------------

HEAD = (
    "Publication date: 27 May 2026\n"
    "Stage 4 Implementation of new TDCV values: 1 July 2026\n"
    "Table 1: Finalised TDCV figures\n"
)
SINGLE = (
    "Electricity – Profile Class 1 (Standard single-rate meters, kWh per year)\n"
    "Usage Level 2023 TDCV 2026 TDCV Change\n"
    "Low 1,800 1,600 -200\n"
    "Medium 2,700 2,500 -200\n"
    "High 4,100 3,800 -300\n"
)
MULTI = (
    "Electricity – Profile Class 2 (Multi-rate meters, kWh per year)\n"
    "Usage Level 2023 TDCV 2026 TDCV Change\n"
    "Low 2,200 1,900 -300\n"
    "Medium 3,900 3,400 -500\n"
    "High 6,700 6,100 -600\n"
)


def test_parse_synthetic_decision_picks_single_rate() -> None:
    levels = parse_decision(HEAD + SINGLE + MULTI)
    assert (levels.low_kwh_per_year, levels.medium_kwh_per_year, levels.high_kwh_per_year) == (
        1600,
        2500,
        3800,
    )


def test_parse_rejects_inconsistent_change() -> None:
    bad = SINGLE.replace("Medium 2,700 2,500 -200", "Medium 2,700 2,600 -200")
    with pytest.raises(IngestError, match="Medium"):
        parse_decision(HEAD + bad)


def test_parse_rejects_missing_table() -> None:
    with pytest.raises(IngestError, match="table header"):
        parse_decision(HEAD + MULTI)


def test_parse_rejects_other_decision_date() -> None:
    with pytest.raises(IngestError, match="publication date"):
        parse_decision(HEAD.replace("27 May", "25 May") + SINGLE)


def test_parse_rejects_missing_row() -> None:
    with pytest.raises(IngestError, match="unexpected row"):
        parse_decision(HEAD + SINGLE.replace("High 4,100 3,800 -300\n", "") + MULTI)


def test_method_sentence_required() -> None:
    check_method("by\ncalculating the lower, median and upper\nquartile of household consumption")
    with pytest.raises(IngestError, match="method"):
        check_method("calculating the mean of household consumption")


def test_missing_pdf_reported(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="--download"):
        pdf_text(tmp_path / "absent.pdf")
