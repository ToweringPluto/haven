"""Generate the illustrative contract examples in ``contracts/examples/``.

Every value here is invented for the API contract and is marked
``"source": "illustrative fixture"``. None of it is real listing data, a real
council tax or energy figure, or a measured model output. Reports embed the
profile, property, cost, findings and signals, so they are built from the same
objects as the per-endpoint files and can't drift from them.

Usage (from ``backend/``)::

    uv run python scripts/make_examples.py          # (re)write the files
    uv run python scripts/make_examples.py --check  # fail if the files are stale
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from haven.api.schemas import FieldError, ProblemDetail, PropertyList
from haven.domain import (
    CostBreakdown,
    Finding,
    Property,
    RenterProfile,
    Report,
    ReportSection,
    ReportSentence,
    Signal,
    SuitabilityAssessment,
    Upload,
)

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "contracts" / "examples"
SOURCE = "illustrative fixture"
AS_OF = date(2026, 11, 1)
CREATED_AT = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
NOTE = "Illustrative value for the API contract; not real data."
SIGNAL_NOTE = "Illustrative output, not a measured model probability."

PERSONAS = ("wheelchair_user", "student", "tight_budget")
ENDPOINT_MODELS: dict[str, type[BaseModel]] = {
    "profile": RenterProfile,
    "properties": PropertyList,
    "cost": CostBreakdown,
    "suitability": SuitabilityAssessment,
    "upload": Upload,
    "report": Report,
}


def ev(value: Any, origin: str, status: str, note: str | None = NOTE) -> dict[str, Any]:
    """An Evidence dict. A null value is always 'insufficient'."""
    return {
        "value": value,
        "origin": origin,
        "source": SOURCE,
        "as_of": AS_OF.isoformat(),
        "status": "insufficient" if value is None else status,
        "note": note,
    }


def missing(origin: str, note: str) -> dict[str, Any]:
    return ev(None, origin, "insufficient", note)


def cost_line(
    kind: str,
    label: str,
    evidence: dict[str, Any],
    low: float | None = None,
    high: float | None = None,
) -> dict[str, Any]:
    return {"kind": kind, "label": label, "monthly_gbp": evidence, "low_gbp": low, "high_gbp": high}


def fact(name: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "evidence": evidence}


def sentence(text: str, *cites: str) -> ReportSentence:
    return ReportSentence(text=text, cites=list(cites))


# --- wheelchair user -------------------------------------------------------------------


def wheelchair_user() -> dict[str, BaseModel]:
    profile = RenterProfile.model_validate(
        {
            "id": "persona-wheelchair-user",
            "label": "Wheelchair user (illustrative persona)",
            "monthly_budget_gbp": 1250,
            "priorities": ["step_free_access", "lift_access", "transport_access"],
            "access": {
                "wheelchair_user": True,
                "step_free_entrance_required": True,
                "lift_required_above_floor": 0,
                "max_walk_to_stop_m": 400,
            },
            "destinations": [
                {
                    "name": "Royal Infirmary of Edinburgh",
                    "latitude": 55.9216,
                    "longitude": -3.1347,
                    "max_travel_minutes": 45,
                }
            ],
        }
    )
    prop = Property.model_validate(
        {
            "id": "ill-prop-leith-flat",
            "title": "Illustrative property — not a real listing: 2-bed flat, Leith",
            "illustrative": True,
            "area": "Leith",
            "latitude": 55.9700,
            "longitude": -3.1720,
            "rent_pcm_gbp": ev(950, "listing", "known"),
            "bedrooms": ev(2, "listing", "known"),
            "property_type": ev("flat", "listing", "known"),
            "floor_area_m2": ev(68, "listing", "known"),
            "council_tax_band": ev("C", "public_data", "known"),
            "epc_rating": ev("C", "public_data", "known"),
            "main_fuel": ev("mains_gas", "public_data", "known"),
            "floor_level": ev(2, "listing", "known"),
            "has_lift": missing("listing", "The listing does not say whether there is a lift."),
            "entrance_steps": ev(3, "listing", "known"),
        }
    )
    cost = CostBreakdown.model_validate(
        {
            "property_id": prop.id,
            "profile_id": profile.id,
            "lines": [
                cost_line("rent", "Rent", ev(950, "listing", "known")),
                cost_line("council_tax", "Council tax (band C)", ev(140, "public_data", "known")),
                cost_line("energy", "Estimated energy", ev(90, "estimate", "estimated"), 70, 115),
            ],
            "total_monthly_gbp": ev(1180, "estimate", "estimated"),
            "total_low_gbp": 1160,
            "total_high_gbp": 1205,
            "budget_monthly_gbp": 1250,
            "budget_comparison": "within",
        }
    )
    findings = [
        Finding.model_validate(f)
        for f in [
            {
                "id": "wu-budget-fit",
                "rule_id": "budget_fit",
                "category": "cost",
                "outcome": "meets",
                "title": "Estimated monthly cost is within budget",
                "reason": "The estimated total, including its upper range, is below the stated "
                "budget.",
                "facts": [fact("total_monthly_gbp", ev(1180, "estimate", "estimated"))],
            },
            {
                "id": "wu-step-free-entrance",
                "rule_id": "step_free_entrance",
                "category": "access",
                "outcome": "concern",
                "title": "Possible entrance steps",
                "reason": "The listing mentions steps at the entrance and a step-free entrance "
                "is required.",
                "facts": [fact("entrance_steps", ev(3, "listing", "known"))],
                "next_step": "Ask the agent for photos of the entrance and whether a ramp or "
                "step-free route is available, and check it in person.",
            },
            {
                "id": "wu-lift-required",
                "rule_id": "lift_required_for_floor",
                "category": "access",
                "outcome": "unknown",
                "title": "Lift availability not stated",
                "reason": "The flat is above the ground floor and the listing does not say "
                "whether there is a lift.",
                "facts": [
                    fact("floor_level", ev(2, "listing", "known")),
                    fact("has_lift", missing("listing", "Not stated in the listing.")),
                ],
                "next_step": "Ask whether the building has a lift, its door width and its "
                "maintenance history.",
            },
            {
                "id": "wu-walk-to-stop",
                "rule_id": "walk_to_stop_within_limit",
                "category": "location",
                "outcome": "meets",
                "title": "Bus stop within the stated walking limit",
                "reason": "The nearest bus stop is estimated to be within the stated limit.",
                "facts": [fact("walk_to_stop_m", ev(180, "estimate", "estimated"))],
            },
        ]
    ]
    signal = Signal.model_validate(
        {
            "id": "wu-sig-entrance-step",
            "kind": "entrance_step",
            "likelihood": "likely",
            "evidence_quality": "good",
            "confidence": None,
            "upload_id": "ill-upload-wu-entrance",
            "source": SOURCE,
            "note": SIGNAL_NOTE,
        }
    )
    upload = Upload.model_validate(
        {
            "id": "ill-upload-wu-entrance",
            "kind": "photo",
            "filename": "entrance.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 482133,
            "uploaded_at": CREATED_AT.isoformat(),
            "property_id": prop.id,
            "metadata_stripped": True,
            "evidence_quality": "good",
            "signals": [signal.model_dump(mode="json")],
        }
    )
    sections = [
        ReportSection(
            heading="What works",
            sentences=[
                sentence(
                    "The estimated monthly cost is within your stated budget.", "wu-budget-fit"
                ),
                sentence(
                    "A bus stop appears to be within your stated walking limit.", "wu-walk-to-stop"
                ),
            ],
        ),
        ReportSection(
            heading="What may be unsuitable",
            sentences=[
                sentence(
                    "The listing and an uploaded photo suggest possible steps at the entrance.",
                    "wu-step-free-entrance",
                    "wu-sig-entrance-step",
                ),
            ],
        ),
        ReportSection(heading="What could be expensive", sentences=[]),
        ReportSection(
            heading="Check before signing",
            sentences=[
                sentence(
                    "Ask whether there is a step-free route into the building.",
                    "wu-step-free-entrance",
                ),
                sentence(
                    "Ask whether the building has a lift and how it is maintained.",
                    "wu-lift-required",
                ),
            ],
        ),
    ]
    return _bundle("wu", profile, prop, cost, findings, upload, sections)


# --- student ---------------------------------------------------------------------------


def student() -> dict[str, BaseModel]:
    profile = RenterProfile.model_validate(
        {
            "id": "persona-student",
            "label": "Student (illustrative persona)",
            "monthly_budget_gbp": 900,
            "priorities": ["total_cost", "transport_access", "travel_time"],
            "destinations": [
                {
                    "name": "University of Edinburgh Central Area",
                    "latitude": 55.9445,
                    "longitude": -3.1892,
                    "max_travel_minutes": 30,
                }
            ],
        }
    )
    prop = Property.model_validate(
        {
            "id": "ill-prop-marchmont-flat",
            "title": "Illustrative property — not a real listing: 1-bed flat, Marchmont",
            "illustrative": True,
            "area": "Marchmont",
            "latitude": 55.9370,
            "longitude": -3.1930,
            "rent_pcm_gbp": ev(825, "listing", "known"),
            "bedrooms": ev(1, "listing", "known"),
            "property_type": ev("flat", "listing", "known"),
            "floor_area_m2": ev(45, "listing", "known"),
            "council_tax_band": missing(
                "listing", "The listing does not state a council tax band."
            ),
            "epc_rating": ev("D", "public_data", "known"),
            "main_fuel": ev("mains_gas", "public_data", "known"),
            "floor_level": ev(3, "listing", "known"),
            "has_lift": ev(False, "listing", "known"),
            "entrance_steps": ev(4, "listing", "known"),
        }
    )
    cost = CostBreakdown.model_validate(
        {
            "property_id": prop.id,
            "profile_id": profile.id,
            "lines": [
                cost_line("rent", "Rent", ev(825, "listing", "known")),
                cost_line(
                    "council_tax",
                    "Council tax (band unknown)",
                    missing(
                        "public_data",
                        "Council tax band unknown, so this line can't be calculated. The "
                        "cost depends on the band (A-H).",
                    ),
                ),
                cost_line("energy", "Estimated energy", ev(70, "estimate", "estimated"), 55, 90),
            ],
            "total_monthly_gbp": missing(
                "estimate", "The total can't be calculated while the council tax line is missing."
            ),
            "total_low_gbp": None,
            "total_high_gbp": None,
            "budget_monthly_gbp": 900,
            "budget_comparison": "unknown",
        }
    )
    findings = [
        Finding.model_validate(f)
        for f in [
            {
                "id": "st-budget-fit",
                "rule_id": "budget_fit",
                "category": "cost",
                "outcome": "unknown",
                "title": "Can't compare the cost with your budget yet",
                "reason": "The council tax band is missing, so the monthly total is incomplete.",
                "facts": [
                    fact(
                        "total_monthly_gbp",
                        missing("estimate", "Total incomplete: council tax unknown."),
                    )
                ],
                "next_step": "Ask the agent for the council tax band, or look the address up "
                "on the Scottish Assessors Association website.",
            },
            {
                "id": "st-council-tax-band",
                "rule_id": "council_tax_band_known",
                "category": "missing_info",
                "outcome": "unknown",
                "title": "Council tax band not stated",
                "reason": "The listing does not include a council tax band.",
                "facts": [
                    fact("council_tax_band", missing("listing", "Not stated in the listing."))
                ],
                "next_step": "Ask the agent for the council tax band before signing.",
            },
            {
                "id": "st-travel-time",
                "rule_id": "travel_time_to_destinations",
                "category": "location",
                "outcome": "meets",
                "title": "Estimated travel time to the university is within your limit",
                "reason": "The estimated walking time to University of Edinburgh Central Area "
                "is within the stated limit.",
                "facts": [fact("walk_minutes", ev(18, "estimate", "estimated"))],
            },
        ]
    ]
    upload = Upload.model_validate(
        {
            "id": "ill-upload-st-tenancy",
            "kind": "document",
            "filename": "draft_tenancy.pdf",
            "content_type": "application/pdf",
            "size_bytes": 213870,
            "uploaded_at": CREATED_AT.isoformat(),
            "property_id": prop.id,
            "metadata_stripped": False,
            "evidence_quality": None,
            "signals": [],
            "extracted_facts": [
                fact(
                    "rent_pcm_gbp",
                    ev(825, "user", "known", "Illustrative value read from draft_tenancy.pdf."),
                ),
                fact(
                    "deposit_gbp",
                    ev(950, "user", "known", "Illustrative value read from draft_tenancy.pdf."),
                ),
            ],
        }
    )
    sections = [
        ReportSection(
            heading="What works",
            sentences=[
                sentence(
                    "The estimated travel time to the university is within your limit.",
                    "st-travel-time",
                )
            ],
        ),
        ReportSection(heading="What may be unsuitable", sentences=[]),
        ReportSection(
            heading="What could be expensive",
            sentences=[
                sentence(
                    "The monthly total is incomplete because the council tax band is unknown.",
                    "st-budget-fit",
                )
            ],
        ),
        ReportSection(
            heading="Check before signing",
            sentences=[
                sentence("Ask the agent for the council tax band.", "st-council-tax-band"),
            ],
        ),
    ]
    return _bundle("st", profile, prop, cost, findings, upload, sections)


# --- tight budget ----------------------------------------------------------------------


def tight_budget() -> dict[str, BaseModel]:
    broadband = {"label": "Broadband", "monthly_gbp": ev(30, "user", "known")}
    profile = RenterProfile.model_validate(
        {
            "id": "persona-tight-budget",
            "label": "Renter on a tight budget (illustrative persona)",
            "monthly_budget_gbp": 1000,
            "priorities": ["total_cost", "heating_cost"],
            "other_recurring_costs": [broadband],
        }
    )
    prop = Property.model_validate(
        {
            "id": "ill-prop-gorgie-flat",
            "title": "Illustrative property — not a real listing: 2-bed flat, Gorgie",
            "illustrative": True,
            "area": "Gorgie",
            "latitude": 55.9380,
            "longitude": -3.2350,
            "rent_pcm_gbp": ev(795, "listing", "known"),
            "bedrooms": ev(2, "listing", "known"),
            "property_type": ev("flat", "listing", "known"),
            "floor_area_m2": ev(60, "listing", "known"),
            "council_tax_band": ev("B", "public_data", "known"),
            "epc_rating": ev("F", "public_data", "known"),
            "main_fuel": ev("electricity", "public_data", "known"),
            "floor_level": ev(1, "listing", "known"),
            "has_lift": ev(False, "listing", "known"),
            "entrance_steps": ev(2, "listing", "known"),
        }
    )
    cost = CostBreakdown.model_validate(
        {
            "property_id": prop.id,
            "profile_id": profile.id,
            "lines": [
                cost_line("rent", "Rent", ev(795, "listing", "known")),
                cost_line("council_tax", "Council tax (band B)", ev(125, "public_data", "known")),
                cost_line("energy", "Estimated energy", ev(185, "estimate", "estimated"), 150, 230),
                cost_line("other", "Broadband", ev(30, "user", "known")),
            ],
            "total_monthly_gbp": ev(1135, "estimate", "estimated"),
            "total_low_gbp": 1100,
            "total_high_gbp": 1180,
            "budget_monthly_gbp": 1000,
            "budget_comparison": "over",
        }
    )
    findings = [
        Finding.model_validate(f)
        for f in [
            {
                "id": "tb-budget-fit",
                "rule_id": "budget_fit",
                "category": "cost",
                "outcome": "concern",
                "title": "Estimated monthly cost is over budget",
                "reason": "Even the low end of the estimated total is above the stated budget.",
                "facts": [fact("total_monthly_gbp", ev(1135, "estimate", "estimated"))],
                "next_step": "Ask for recent energy bills and check whether the rent is "
                "negotiable.",
            },
            {
                "id": "tb-epc-heating-cost",
                "rule_id": "epc_heating_cost_risk",
                "category": "cost",
                "outcome": "concern",
                "title": "Heating costs could be high",
                "reason": "EPC band F with electric heating suggests higher than average "
                "energy costs.",
                "facts": [
                    fact("epc_rating", ev("F", "public_data", "known")),
                    fact("main_fuel", ev("electricity", "public_data", "known")),
                ],
                "next_step": "Ask what the heating system is and for the last year's energy bills.",
            },
            {
                "id": "tb-council-tax-band",
                "rule_id": "council_tax_band_known",
                "category": "missing_info",
                "outcome": "meets",
                "title": "Council tax band known",
                "reason": "The council tax band is available from public data.",
                "facts": [fact("council_tax_band", ev("B", "public_data", "known"))],
            },
        ]
    ]
    signals = [
        Signal.model_validate(s)
        for s in [
            {
                "id": "tb-sig-damp",
                "kind": "possible_damp",
                "likelihood": "possible",
                "evidence_quality": "limited",
                "confidence": None,
                "upload_id": "ill-upload-tb-bathroom",
                "source": SOURCE,
                "note": SIGNAL_NOTE,
            },
            {
                "id": "tb-sig-mould",
                "kind": "possible_mould",
                "likelihood": "insufficient_evidence",
                "evidence_quality": "limited",
                "confidence": None,
                "upload_id": "ill-upload-tb-bathroom",
                "source": SOURCE,
                "note": "Illustrative output: the photo is too dark to judge.",
            },
        ]
    ]
    upload = Upload.model_validate(
        {
            "id": "ill-upload-tb-bathroom",
            "kind": "photo",
            "filename": "bathroom_ceiling.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 356201,
            "uploaded_at": CREATED_AT.isoformat(),
            "property_id": prop.id,
            "metadata_stripped": True,
            "evidence_quality": "limited",
            "signals": [s.model_dump(mode="json") for s in signals],
        }
    )
    sections = [
        ReportSection(
            heading="What works",
            sentences=[sentence("The council tax band is known.", "tb-council-tax-band")],
        ),
        ReportSection(
            heading="What may be unsuitable",
            sentences=[
                sentence(
                    "Possible damp in the uploaded bathroom photo; inspect before signing.",
                    "tb-sig-damp",
                ),
            ],
        ),
        ReportSection(
            heading="What could be expensive",
            sentences=[
                sentence("The estimated monthly cost is over your stated budget.", "tb-budget-fit"),
                sentence(
                    "Heating costs could be high for an EPC band F flat with electric heating.",
                    "tb-epc-heating-cost",
                ),
            ],
        ),
        ReportSection(
            heading="Check before signing",
            sentences=[
                sentence(
                    "There is not enough evidence to say anything about mould; ask to see the "
                    "bathroom in daylight.",
                    "tb-sig-mould",
                ),
                sentence("Ask for the last year's energy bills.", "tb-epc-heating-cost"),
            ],
        ),
    ]
    return _bundle("tb", profile, prop, cost, findings, upload, sections)


# --- assembly --------------------------------------------------------------------------


def _bundle(
    prefix: str,
    profile: RenterProfile,
    prop: Property,
    cost: CostBreakdown,
    findings: list[Finding],
    upload: Upload,
    sections: list[ReportSection],
) -> dict[str, BaseModel]:
    report = Report(
        id=f"ill-report-{prefix}",
        created_at=CREATED_AT,
        illustrative=True,
        profile=profile,
        property=prop,
        cost=cost,
        findings=findings,
        signals=upload.signals,
        sections=sections,
    )
    return {
        "profile": profile,
        "properties": PropertyList(items=[prop]),
        "cost": cost,
        "suitability": SuitabilityAssessment(
            property_id=prop.id, profile_id=profile.id, findings=findings
        ),
        "upload": upload,
        "report": report,
    }


def errors() -> dict[str, BaseModel]:
    return {
        "not_found": ProblemDetail(
            title="Not Found",
            status=404,
            detail="No property with id 'ill-prop-does-not-exist'.",
            instance="/v1/properties/ill-prop-does-not-exist",
        ),
        "validation_error": ProblemDetail(
            title="Unprocessable Content",
            status=422,
            detail="The request body failed validation.",
            instance="/v1/profiles",
            errors=[
                FieldError(
                    loc=["body", "monthly_budget_gbp"],
                    msg="Input should be greater than 0",
                    type="greater_than",
                )
            ],
        ),
    }


def build_examples() -> dict[Path, str]:
    """Relative path -> JSON text for every example file."""
    builders = {
        "wheelchair_user": wheelchair_user,
        "student": student,
        "tight_budget": tight_budget,
    }
    out: dict[Path, str] = {}
    for persona in PERSONAS:
        for endpoint, model in builders[persona]().items():
            out[Path(persona) / f"{endpoint}.json"] = model.model_dump_json(indent=2) + "\n"
    for name, problem in errors().items():
        out[Path("errors") / f"{name}.json"] = problem.model_dump_json(indent=2) + "\n"
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="fail if files are out of date")
    args = parser.parse_args(argv)

    stale: list[Path] = []
    for rel, text in build_examples().items():
        path = EXAMPLES_DIR / rel
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    if stale:
        print("Out of date (run scripts/make_examples.py):", *map(str, stale), sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
