"""SAP 10.2 heating efficiency reference data: committed YAML, schema and parser."""

import pytest
from pydantic import ValidationError

from haven.domain import MainFuel
from haven.reference import HeatingEfficiencyReference, load_heating_efficiency
from scripts import ingest_heating_efficiency as ingest
from scripts.ingest_heating_efficiency import (
    CAT_BOILERS,
    GAS_1998,
    IngestError,
    parse_sources,
    parse_tables,
)


@pytest.fixture(scope="module")
def reference() -> HeatingEfficiencyReference:
    return load_heating_efficiency()


def by_code(reference: HeatingEfficiencyReference, fuel: MainFuel) -> dict[int, int]:
    return {s.code: s.space_efficiency_pct for s in reference.fuels[fuel].systems}


def test_committed_gas_values(reference: HeatingEfficiencyReference) -> None:
    # SAP 10.2 (11-04-2023) Table 4b, winter efficiency column.
    gas = by_code(reference, MainFuel.mains_gas)
    assert gas[102] == gas[104] == 84  # condensing, 1998 or later
    assert gas[101] == gas[103] == 74  # non-condensing, 1998 or later
    assert gas[116] == 56  # regular floor mounted, pre 1979
    fuel = reference.fuels[MainFuel.mains_gas]
    assert (fuel.central_pct, fuel.lowest_pct, fuel.highest_pct) == (84, 56, 84)
    summer = {s.code: s.water_efficiency_pct for s in fuel.systems}
    assert summer[104] == 75 and summer[116] == 46


def test_committed_electric_values(reference: HeatingEfficiencyReference) -> None:
    # SAP 10.2 Table 4a: resistive electric heating 100%, heat pumps "in other cases" 170%.
    electric = by_code(reference, MainFuel.electricity)
    assert electric[402] == electric[691] == electric[409] == 100
    assert electric[221] == electric[223] == electric[224] == 170
    fuel = reference.fuels[MainFuel.electricity]
    assert (fuel.central_pct, fuel.lowest_pct, fuel.highest_pct) == (100, 100, 170)


def test_selection_rules(reference: HeatingEfficiencyReference) -> None:
    for fuel in reference.fuels.values():
        assert all(s.rdsap for s in fuel.systems)
    gas = reference.fuels[MainFuel.mains_gas]
    assert {s.table for s in gas.systems} == {"4b"}
    assert all(s.group.startswith("Gas boilers") for s in gas.systems)
    # Low flow temperature heat pumps (codes 211/213/214) need evidence a listing doesn't give.
    electric = by_code(reference, MainFuel.electricity)
    assert not {211, 213, 214} & set(electric)
    assert reference.for_fuel(MainFuel.other) is None


def test_provenance(reference: HeatingEfficiencyReference) -> None:
    assert reference.meta.source_url == ingest.SOURCE_URL == reference.source_url
    assert reference.document == "SAP 10.2 (11-04-2023)"
    assert "Crown copyright" in reference.meta.licence
    assert "not stated on the document" in reference.meta.licence
    assert "not measurements" in reference.meta.notes


def test_reparse_raw_pdf_matches_yaml(reference: HeatingEfficiencyReference) -> None:
    if not ingest.RAW_PDF.is_file():
        pytest.skip("raw SAP 10.2 PDF not present (run ingest_heating_efficiency.py --download)")
    parsed = HeatingEfficiencyReference.model_validate(
        {"meta": reference.meta.model_dump(), **parse_sources()}
    )
    assert parsed == reference


def test_check_mode_passes() -> None:
    assert ingest.main(["--check"]) == 0


# --- schema --------------------------------------------------------------------------------


def test_central_code_must_match_efficiency(reference: HeatingEfficiencyReference) -> None:
    data = reference.model_dump(mode="json")
    data["fuels"]["mains_gas"]["central_codes"] = [101]
    with pytest.raises(ValidationError, match="different efficiency"):
        HeatingEfficiencyReference.model_validate(data)


def test_central_code_must_be_listed(reference: HeatingEfficiencyReference) -> None:
    data = reference.model_dump(mode="json")
    data["fuels"]["mains_gas"]["central_codes"] = [999]
    with pytest.raises(ValidationError, match="not among the systems"):
        HeatingEfficiencyReference.model_validate(data)


def test_both_fuels_required(reference: HeatingEfficiencyReference) -> None:
    data = reference.model_dump(mode="json")
    del data["fuels"]["electricity"]
    with pytest.raises(ValidationError, match="mains_gas and electricity"):
        HeatingEfficiencyReference.model_validate(data)


def test_non_rdsap_rows_rejected(reference: HeatingEfficiencyReference) -> None:
    data = reference.model_dump(mode="json")
    data["fuels"]["mains_gas"]["systems"][0]["rdsap"] = False
    with pytest.raises(ValidationError):
        HeatingEfficiencyReference.model_validate(data)


# --- parser on synthetic text --------------------------------------------------------------

SYNTHETIC = "\n".join(
    [
        "Version 10.2 (11-04-2023)",
        "Table 4a: Heating systems (space and water)",
        CAT_BOILERS,
        "Direct acting electric boiler 100 From Table 4d 191 rd",
        "Electric dry core storage boiler in unheated space a) b) 85 2 0.75 194",
        "Category 4 : HEAT PUMPS WITH RADIATORS OR UNDERFLOOR HEATING",
        "Air source heat pump in other cases 170 170 From Table 4d 224 rd",
        "Category 7 : ELECTRIC STORAGE SYSTEMS",
        "Slimline storage heaters 100 5 0.2 402 rd",
        "Slimline storage heaters 100 4 0.4 402 rd",
        "Category 8 : ELECTRIC UNDERFLOOR HEATING",
        "In timber floor, or immediately below floor covering 100 1 1 425",
        "Table 4b: Seasonal efficiency for gas and liquid fuel boilers",
        GAS_1998,
        "Condensing combi with automatic ignition 84 75 104 rd",
        "Regular condensing with permanent pilot light 80 70 106",
        "Table 4c: Efficiency adjustments",
    ]
)


def test_parse_synthetic_tables() -> None:
    table_4a, table_4b = parse_tables(SYNTHETIC)
    assert (table_4a[191].a, table_4a[191].b, table_4a[191].group) == (100, None, CAT_BOILERS)
    assert (table_4a[224].a, table_4a[224].b) == (170, 170)
    assert table_4a[194].rdsap is False and table_4a[194].a == 85
    assert table_4a[402].a == 100  # listed twice (off-peak and 24-hour), same efficiency
    assert table_4a[425].a == 100
    assert (table_4b[104].a, table_4b[104].b, table_4b[104].group) == (84, 75, GAS_1998)
    assert table_4b[106].rdsap is False
    assert 104 not in table_4a


def test_parse_rejects_conflicting_duplicates() -> None:
    bad = SYNTHETIC.replace("Slimline storage heaters 100 4 0.4 402 rd", "Slimline 90 4 0.4 402")
    with pytest.raises(IngestError, match="402"):
        parse_tables(bad)


def test_parse_requires_version_and_headings() -> None:
    with pytest.raises(IngestError, match="version"):
        parse_tables(SYNTHETIC.replace("Version 10.2", "Version 10.3"))
    with pytest.raises(IngestError, match="Table 4c"):
        parse_tables(SYNTHETIC.replace("Table 4c: Efficiency adjustments", ""))


def test_wanted_row_checks() -> None:
    with pytest.raises(IngestError, match="not found"):
        ingest.build_fuels(SYNTHETIC)  # most wanted rows are absent from the synthetic text
    table_4a, table_4b = parse_tables(SYNTHETIC)
    wanted = ingest.Wanted("4b", 104, GAS_1998, "Condensing combi")
    assert ingest._system(table_4b[104], wanted).space_efficiency_pct == 84
    with pytest.raises(IngestError, match="expected 'Regular"):
        ingest._system(table_4b[104], ingest.Wanted("4b", 104, GAS_1998, "Regular"))
    with pytest.raises(IngestError, match="is under"):
        ingest._system(table_4b[104], ingest.Wanted("4b", 104, ingest.GAS_FAN, "Condensing"))
    with pytest.raises(IngestError, match="not marked 'rd'"):
        ingest._system(table_4b[106], ingest.Wanted("4b", 106, GAS_1998, "Regular"))
