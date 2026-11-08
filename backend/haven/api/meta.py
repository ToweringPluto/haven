"""Enum values with human-readable labels, served by ``GET /v1/meta/enums``.

Labels follow the honesty rules: signals and likelihoods are phrased as
possibilities, ``unknown`` is never worded as a concern, and
``insufficient_evidence`` is shown as "Insufficient evidence".
"""

from enum import StrEnum

from haven.api.schemas import EnumCatalog, EnumOption
from haven.domain import (
    BudgetComparison,
    CostKind,
    CouncilTaxBand,
    EpcBand,
    EvidenceQuality,
    FindingCategory,
    Likelihood,
    MainFuel,
    Origin,
    Outcome,
    Priority,
    PropertyType,
    SignalKind,
    Status,
    UploadKind,
)

LABELS: dict[str, tuple[type[StrEnum], dict[str, str]]] = {
    "origin": (
        Origin,
        {
            "listing": "From the listing",
            "public_data": "Public data",
            "user": "Supplied by you",
            "model": "Inferred by a model",
            "estimate": "Estimate",
        },
    ),
    "status": (
        Status,
        {
            "known": "Known",
            "estimated": "Estimated",
            "inferred": "Inferred",
            "uncertain": "Uncertain",
            "insufficient": "Insufficient evidence",
        },
    ),
    "outcome": (
        Outcome,
        {
            "meets": "Meets your requirement",
            "concern": "Possible concern",
            "unknown": "Unknown: needs checking",
        },
    ),
    "likelihood": (
        Likelihood,
        {
            "unlikely": "Unlikely",
            "possible": "Possible",
            "likely": "Likely",
            "insufficient_evidence": "Insufficient evidence",
        },
    ),
    "evidence_quality": (
        EvidenceQuality,
        {"good": "Good", "limited": "Limited", "poor": "Poor"},
    ),
    "finding_category": (
        FindingCategory,
        {
            "cost": "Cost",
            "access": "Access",
            "location": "Location",
            "condition": "Condition",
            "missing_info": "Missing information",
        },
    ),
    "budget_comparison": (
        BudgetComparison,
        {
            "within": "Estimated within budget",
            "over": "Estimated over budget",
            "unknown": "Unknown: not enough information",
        },
    ),
    "council_tax_band": (CouncilTaxBand, {b.value: f"Band {b.value}" for b in CouncilTaxBand}),
    "epc_band": (EpcBand, {b.value: f"EPC {b.value}" for b in EpcBand}),
    "property_type": (
        PropertyType,
        {
            "flat": "Flat",
            "maisonette": "Maisonette",
            "house": "House",
            "bungalow": "Bungalow",
            "other": "Other",
        },
    ),
    "main_fuel": (
        MainFuel,
        {"mains_gas": "Mains gas", "electricity": "Electricity", "other": "Other"},
    ),
    "cost_kind": (
        CostKind,
        {
            "rent": "Rent",
            "council_tax": "Council tax",
            "energy": "Energy (estimated)",
            "other": "Other recurring cost",
        },
    ),
    "signal_kind": (
        SignalKind,
        {
            "possible_damp": "Possible damp",
            "possible_mould": "Possible mould",
            "entrance_step": "Possible entrance step",
        },
    ),
    "upload_kind": (
        UploadKind,
        {"photo": "Photo", "document": "Document"},
    ),
    "priority": (
        Priority,
        {
            "total_cost": "Total monthly cost",
            "step_free_access": "Step-free access",
            "lift_access": "Lift access",
            "transport_access": "Public transport access",
            "travel_time": "Travel time to destinations",
            "heating_cost": "Heating cost",
            "space": "Space",
            "nearby_schools": "Nearby schools",
            "property_condition": "Property condition",
        },
    ),
}


def enum_catalog() -> EnumCatalog:
    enums: dict[str, list[EnumOption]] = {}
    for name, (enum, labels) in LABELS.items():
        missing = {m.value for m in enum} ^ set(labels)
        if missing:
            raise ValueError(f"labels for {name} don't match the enum: {sorted(missing)}")
        enums[name] = [EnumOption(value=m.value, label=labels[m.value]) for m in enum]
    return EnumCatalog(enums=enums)
