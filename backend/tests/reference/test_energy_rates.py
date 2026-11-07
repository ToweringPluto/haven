"""Ofgem price cap reference data: committed YAML, schema checks, table parser, cross-check."""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from haven.reference import EnergyRatesReference, FuelRates, load_energy_rates
from scripts import ingest_energy_rates as ingest
from scripts.ingest_energy_rates import (
    CAP_LEVELS,
    PERIOD,
    TABLES,
    IngestError,
    Period,
    cross_check,
    derive_rates,
    parse_cap_levels,
    parse_fuel,
    parse_table,
)

# Sanity bounds from the task: anything outside these is a parsing or unit error.
UNIT_BOUNDS = {"electricity": (10.0, 60.0), "gas": (2.0, 20.0)}


@pytest.fixture(scope="module")
def reference() -> EnergyRatesReference:
    return load_energy_rates()


def test_committed_file_fields(reference: EnergyRatesReference) -> None:
    assert reference.region == "Southern Scotland"
    assert reference.payment_method == "direct_debit"
    assert reference.electricity_meter == "single_rate"
    assert reference.prices_include_vat is True
    assert (reference.valid_from, reference.valid_to) == (date(2026, 10, 1), date(2026, 12, 31))


@pytest.mark.parametrize("fuel", ["electricity", "gas"])
def test_rates_within_sane_bounds(reference: EnergyRatesReference, fuel: str) -> None:
    rates: FuelRates = getattr(reference, fuel)
    low, high = UNIT_BOUNDS[fuel]
    assert low <= rates.unit_rate_p_per_kwh <= high
    assert 0 < rates.standing_charge_p_per_day < 150


def test_vat_as_stated_by_ofgem(reference: EnergyRatesReference) -> None:
    assert reference.gas.vat_rate == 0.05
    assert reference.electricity.vat_rate == 0.0


def test_provenance_points_at_ofgem(reference: EnergyRatesReference) -> None:
    assert reference.meta.source_url.startswith("https://www.ofgem.gov.uk/")
    assert "Open Government Licence" in reference.meta.licence
    for table in TABLES:
        assert getattr(reference, table.fuel).source_url == table.url


def test_covers(reference: EnergyRatesReference) -> None:
    assert reference.covers(date(2026, 11, 7))
    assert reference.covers(date(2026, 10, 1)) and reference.covers(date(2026, 12, 31))
    assert not reference.covers(date(2027, 1, 1))
    assert not reference.covers(date(2026, 9, 30))


@pytest.mark.parametrize("table", TABLES, ids=lambda t: t.fuel)
def test_reparse_raw_table_matches_yaml(
    table: ingest.Table, reference: EnergyRatesReference
) -> None:
    if not table.path.is_file():
        pytest.skip(f"raw table {table.path} not present (run ingest_energy_rates.py --download)")
    assert parse_fuel(table) == getattr(reference, table.fuel)


def test_cross_check_with_cap_levels_pdf(reference: EnergyRatesReference) -> None:
    if not CAP_LEVELS.path.is_file():
        pytest.skip(f"{CAP_LEVELS.path} not present (run ingest_energy_rates.py --download)")
    assert cross_check(reference, CAP_LEVELS.path) == []


def test_check_mode_passes() -> None:
    assert ingest.main(["--check"]) == 0


# --- schema --------------------------------------------------------------------------------


def test_period_must_be_ordered(reference: EnergyRatesReference) -> None:
    data = reference.model_dump(mode="json")
    data["valid_to"] = "2026-09-01"
    with pytest.raises(ValidationError, match="valid_to"):
        EnergyRatesReference.model_validate(data)


def test_other_region_rejected(reference: EnergyRatesReference) -> None:
    data = reference.model_dump(mode="json")
    data["region"] = "London"
    with pytest.raises(ValidationError):
        EnergyRatesReference.model_validate(data)


def test_missing_fuel_rejected(reference: EnergyRatesReference) -> None:
    data = reference.model_dump(mode="json")
    del data["gas"]
    with pytest.raises(ValidationError, match="gas"):
        EnergyRatesReference.model_validate(data)


# --- everviz table parser on synthetic input -----------------------------------------------

SYNTHETIC_PERIOD = Period("January to March 2030", date(2030, 1, 1), date(2030, 3, 31))
SYNTHETIC_TABLE = ingest.Table(
    "gas",
    "https://example.invalid/inject/x/",
    "x.js",
    "Gas standing charges and unit rates paid by Direct Debit",
    0.05,
)


def _everviz(title: str, rows: list[list[str]]) -> str:
    header = [
        "Region",
        "Daily standing charge January to March 2030",
        "Unit rate  January to March 2030",
    ]
    options = {"data": {"value": [header, *rows]}, "options": {"title": {"text": title}}}
    return f"(function () {{\n  var options = {json.dumps(options)};\n  function f() {{}}\n}}());\n"


ROWS = [
    ["London", "30.00 pence per day", "8.00 pence per kWh"],
    ["Southern Scotland", "31.50 pence per day", "7.25 pence per kWh"],
]
TITLE = "<h3>Gas standing charges and unit rates paid by Direct Debit</h3><h3></h3>"


def test_parse_synthetic_table() -> None:
    text = _everviz(TITLE, ROWS)
    assert parse_table(text, SYNTHETIC_TABLE, SYNTHETIC_PERIOD) == (31.50, 7.25)


def test_parse_rejects_wrong_title() -> None:
    text = _everviz("<h3>Electricity standing charges, multi-rate</h3>", ROWS)
    with pytest.raises(IngestError, match="title"):
        parse_table(text, SYNTHETIC_TABLE, SYNTHETIC_PERIOD)


def test_parse_rejects_other_period() -> None:
    with pytest.raises(IngestError, match=PERIOD.label):
        parse_table(_everviz(TITLE, ROWS), SYNTHETIC_TABLE, PERIOD)


def test_parse_rejects_missing_region() -> None:
    with pytest.raises(IngestError, match="Southern Scotland"):
        parse_table(_everviz(TITLE, ROWS[:1]), SYNTHETIC_TABLE, SYNTHETIC_PERIOD)


def test_parse_rejects_wrong_unit() -> None:
    rows = [["Southern Scotland", "31.50 pence per kWh", "7.25 pence per kWh"]]
    with pytest.raises(IngestError, match="pence per day"):
        parse_table(_everviz(TITLE, rows), SYNTHETIC_TABLE, SYNTHETIC_PERIOD)


def test_parse_rejects_non_everviz_text() -> None:
    with pytest.raises(IngestError, match="options"):
        parse_table("<html></html>", SYNTHETIC_TABLE, SYNTHETIC_PERIOD)


# --- cap levels parser and derivation ------------------------------------------------------

GAS_PAGE = """Benchmark Maximum Charges
Gas
Other Payment Method
Region, i Nil kWh m (9,500
kWh)
London £100.00 £800.00
Southern Scotland £109.50 £1,059.50
"""
ELEC_PAGE = """Electricity
Other Payment Method
Single-Rate Single-Rate Multi- Multi-
Region, i
£200.00 £900.00 £201.00 £1,100.00
Southern Scotland
London £150.00 £800.00 £151.00 £1,000.00
"""
CREDIT_PAGE = """Standard Credit
Region, i Nil kWh m (9,500
Southern Scotland £999.00 £9,999.00
"""


def test_parse_cap_levels_handles_wrapped_rows() -> None:
    levels = parse_cap_levels([GAS_PAGE, CREDIT_PAGE, ELEC_PAGE])
    assert levels == {"gas": (109.50, 1059.50), "electricity": (200.00, 900.00)}


def test_parse_cap_levels_requires_both_fuels() -> None:
    with pytest.raises(IngestError, match="electricity"):
        parse_cap_levels([GAS_PAGE])


def test_derive_rates() -> None:
    gas = derive_rates(109.50, 1059.50, "gas", 0.05)
    assert gas["standing_charge_p_per_day"] == pytest.approx(30.0 * 1.05)
    assert gas["unit_rate_p_per_kwh"] == pytest.approx(10.0 * 1.05)
    elec = derive_rates(365.00, 2865.00, "electricity", 0.0)
    assert elec == pytest.approx({"standing_charge_p_per_day": 100.0, "unit_rate_p_per_kwh": 100.0})
