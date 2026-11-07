"""Edinburgh council tax reference data: committed YAML, schema checks and the PDF parser."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from haven.domain import CouncilTaxBand
from haven.reference import BandCharges, CouncilTaxReference, load_council_tax
from haven.reference.council_tax import to_pence
from scripts import ingest_council_tax as ingest
from scripts.ingest_council_tax import SOURCES, IngestError, parse_charges, parse_source

YEARS = [s.year for s in SOURCES]


@pytest.fixture(scope="module")
def reference() -> CouncilTaxReference:
    return load_council_tax()


def test_committed_file_has_every_year_and_band(reference: CouncilTaxReference) -> None:
    assert list(reference.years) == YEARS
    for year in reference.years.values():
        assert list(year.bands) == list(CouncilTaxBand)


def test_totals_equal_components(reference: CouncilTaxReference) -> None:
    for key, year in reference.years.items():
        for band, c in year.bands.items():
            parts = to_pence(c.council_tax_gbp) + to_pence(c.water_gbp)
            parts += to_pence(c.waste_water_gbp)
            assert parts == to_pence(c.total_gbp), (key, band)


def test_sanity_anchor_2025_band_a(reference: CouncilTaxReference) -> None:
    a = reference.years["2025/26"].bands[CouncilTaxBand.A]
    assert (a.council_tax_gbp, a.water_gbp, a.waste_water_gbp, a.total_gbp) == (
        1042.34,
        185.28,
        214.98,
        1442.60,
    )


def test_provenance_points_at_official_pdfs(reference: CouncilTaxReference) -> None:
    assert reference.meta.source_url.startswith("https://www.edinburgh.gov.uk/")
    for source in SOURCES:
        year = reference.years[source.year]
        assert year.source_url == source.url
        assert year.valid_from == date(int(source.year[:4]), 4, 1)


def test_year_for(reference: CouncilTaxReference) -> None:
    assert reference.year_for(date(2026, 11, 7)) is reference.years["2026/27"]
    assert reference.year_for(date(2025, 4, 1)) is reference.years["2025/26"]
    assert reference.year_for(date(2020, 1, 1)) is None


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s.year)
def test_reparse_raw_pdf_matches_yaml(source: Any, reference: CouncilTaxReference) -> None:
    if not source.path.is_file():
        pytest.skip(f"raw PDF {source.path} not present (run ingest_council_tax.py --download)")
    assert parse_source(source) == reference.years[source.year]


def test_check_mode_passes() -> None:
    assert ingest.main(["--check"]) == 0


# --- schema --------------------------------------------------------------------------------


def test_band_total_mismatch_rejected() -> None:
    with pytest.raises(ValidationError, match="total"):
        BandCharges(council_tax_gbp=1.00, water_gbp=1.00, waste_water_gbp=1.00, total_gbp=3.01)


def test_missing_band_rejected(reference: CouncilTaxReference) -> None:
    data = reference.model_dump(mode="json")
    del data["years"]["2025/26"]["bands"]["H"]
    with pytest.raises(ValidationError, match="missing bands"):
        CouncilTaxReference.model_validate(data)


def test_year_key_must_match_validity(reference: CouncilTaxReference) -> None:
    data = reference.model_dump(mode="json")
    data["years"]["2024/25"] = data["years"].pop("2025/26")
    with pytest.raises(ValidationError, match="doesn't match"):
        CouncilTaxReference.model_validate(data)


# --- parser on synthetic text (no PDF needed) ----------------------------------------------

SYNTHETIC = """Council Tax charges 2030/31
Band Council Tax 2029/30 Council Tax 2030/31
A £900.00 £1,000.00
Band Water Sewerage Total
2030/31
A £1,000.00 £100.00 £110.00 £1,210.00
B £1,100.00 £110.00 £120.00 £1,330.00
C £1,200.00 £120.00 £130.00 £1,450.00
D £1,300.00 £130.00 £140.00 £1,570.00
E £1,400.00 £140.00 £150.00 £1,690.00
F £1,500.00 £150.00 £160.00 £1,810.00
G £1,600.00 £160.00 £170.00 £1,930.00
H £1,700.00 £170.00 £180.00 £2,050.00
"""


def test_parse_synthetic_table() -> None:
    bands = parse_charges(SYNTHETIC, "2030/31")
    assert list(bands) == list(CouncilTaxBand)
    assert bands[CouncilTaxBand.A] == BandCharges(
        council_tax_gbp=1000.00, water_gbp=100.00, waste_water_gbp=110.00, total_gbp=1210.00
    )


def test_parse_rejects_wrong_year() -> None:
    with pytest.raises(IngestError, match="2031/32"):
        parse_charges(SYNTHETIC, "2031/32")


def test_parse_rejects_missing_band() -> None:
    text = "\n".join(line for line in SYNTHETIC.splitlines() if not line.startswith("H "))
    with pytest.raises(IngestError, match="H"):
        parse_charges(text, "2030/31")


def test_parse_rejects_bad_total() -> None:
    text = SYNTHETIC.replace("£1,210.00", "£1,211.00")
    with pytest.raises(ValidationError, match="total"):
        parse_charges(text, "2030/31")


def test_parse_rejects_duplicate_band() -> None:
    text = SYNTHETIC + "A £1,000.00 £100.00 £110.00 £1,210.00\n"
    with pytest.raises(IngestError, match="twice"):
        parse_charges(text, "2030/31")
