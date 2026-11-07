"""Conflict findings: a renter's document disagrees with the listing on EPC, band or rent."""

from typing import Any

import pytest

from haven.domain import CitedFact, FindingCategory, Outcome, Property, RenterProfile
from haven.rules.conflicts import conflict_findings

PROFILE = RenterProfile(id="r", label="Renter")


def ev(value: Any, status: str = "known") -> dict[str, Any]:
    return {
        "value": value,
        "origin": "listing",
        "source": "Example listing",
        "status": "insufficient" if value is None else status,
    }


def prop(**overrides: Any) -> Property:
    data: dict[str, Any] = {
        "id": "p",
        "title": "Test flat",
        "rent_pcm_gbp": ev(950.0),
        "bedrooms": ev(2),
        "property_type": ev("flat"),
        "floor_area_m2": ev(60.0),
        "council_tax_band": ev("C"),
        "epc_rating": ev("D"),
        "main_fuel": ev("mains_gas"),
        "floor_level": ev(0),
        "has_lift": ev(False),
        "entrance_steps": ev(0),
    }
    data.update(overrides)
    return Property.model_validate(data)


def doc(name: str, value: Any, source: str = "lease.pdf", status: str = "known") -> CitedFact:
    return CitedFact.model_validate(
        {
            "name": name,
            "evidence": {
                "value": value,
                "origin": "user",
                "source": source,
                "status": "insufficient" if value is None else status,
            },
        }
    )


@pytest.mark.parametrize(
    ("name", "value", "label"),
    [
        ("epc_rating", "F", "EPC rating"),
        ("council_tax_band", "E", "council tax band"),
        ("rent_pcm_gbp", 1050.0, "monthly rent"),
    ],
)
def test_disagreement_is_a_concern_citing_both_sources(name: str, value: Any, label: str) -> None:
    (finding,) = conflict_findings(prop(), PROFILE, [doc(name, value)])
    assert finding.outcome is Outcome.concern
    assert finding.category is FindingCategory.cost
    assert label in finding.title
    assert "Example listing" in finding.reason and "lease.pdf" in finding.reason
    assert [f.name for f in finding.facts] == [f"listed_{name}", f"document_{name}"]
    assert finding.facts[0].evidence.origin == "listing"
    assert finding.facts[1].evidence.origin == "user"
    assert finding.next_step and "which" in finding.next_step and "correct" in finding.next_step


def test_agreement_and_missing_values_raise_nothing() -> None:
    facts = [
        doc("epc_rating", "D"),
        doc("council_tax_band", "c"),  # case doesn't matter
        doc("rent_pcm_gbp", 950.4),  # within £1
        doc("deposit_gbp", 1200.0),  # not on the property: nothing to compare
        doc("epc_rating", None),  # not found in the document
    ]
    assert conflict_findings(prop(), PROFILE, facts) == []
    assert (
        conflict_findings(prop(council_tax_band=ev(None)), PROFILE, [doc("council_tax_band", "B")])
        == []
    )


def test_ocr_values_are_flagged_as_possible_misreads() -> None:
    (finding,) = conflict_findings(
        prop(), PROFILE, [doc("epc_rating", "B", "scan.png", "uncertain")]
    )
    assert "OCR" in finding.reason and "misreading" in finding.reason


def test_one_finding_per_document_and_field() -> None:
    findings = conflict_findings(
        prop(),
        PROFILE,
        [
            doc("rent_pcm_gbp", 1000.0, "lease.pdf"),
            doc("rent_pcm_gbp", 990.0, "letter.pdf"),
            doc("epc_rating", "G"),
        ],
    )
    assert sorted(f.id for f in findings) == [
        "p:r:document_conflict:epc_rating:lease.pdf",
        "p:r:document_conflict:rent_pcm_gbp:lease.pdf",
        "p:r:document_conflict:rent_pcm_gbp:letter.pdf",
    ]
    assert "£950 a month" in findings[0].reason or "£950 a month" in findings[1].reason
