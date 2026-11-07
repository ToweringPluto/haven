"""Findings for facts where a renter's document disagrees with the listing/property record.

Document facts come from :func:`haven.screening.documents.extract_document` (also stored on
``Upload.extracted_facts``). When a document gives a value for the EPC rating, council tax
band or rent and it differs from the property's value, Haven raises a ``concern`` that cites
both sources and asks the renter to check with the landlord. It doesn't decide which one is
right. Matching values, or a missing value on either side, raise nothing.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from haven.domain import (
    CitedFact,
    Evidence,
    Finding,
    FindingCategory,
    Outcome,
    Property,
    RenterProfile,
    Status,
)

RULE_ID = "document_conflict"
RENT_TOLERANCE_GBP = 1.0  # rents within £1 (e.g. £950 vs £950.00) are the same


@dataclass(frozen=True)
class _Check:
    document_field: str
    label: str
    category: FindingCategory


CHECKS = (
    _Check("epc_rating", "EPC rating", FindingCategory.cost),
    _Check("council_tax_band", "council tax band", FindingCategory.cost),
    _Check("rent_pcm_gbp", "monthly rent", FindingCategory.cost),
)


def _property_evidence(prop: Property, document_field: str) -> Evidence[object]:
    evidence: Evidence[object] = {
        "epc_rating": prop.epc_rating,
        "council_tax_band": prop.council_tax_band,
        "rent_pcm_gbp": prop.rent_pcm_gbp,
    }[document_field]  # type: ignore[assignment]
    return evidence


def _plain(value: object) -> object:
    return getattr(value, "value", value)  # enums -> their string value


def _differs(document_field: str, listed: object, document: object) -> bool:
    if document_field == "rent_pcm_gbp":
        assert isinstance(listed, int | float) and isinstance(document, int | float)
        return abs(float(listed) - float(document)) >= RENT_TOLERANCE_GBP
    return str(_plain(listed)).upper() != str(_plain(document)).upper()


def _show(document_field: str, value: object) -> str:
    if document_field == "rent_pcm_gbp":
        assert isinstance(value, int | float)
        return f"£{float(value):,.0f} a month"
    return str(_plain(value))


def conflict_findings(
    prop: Property, profile: RenterProfile, document_facts: Iterable[CitedFact]
) -> list[Finding]:
    """One ``concern`` per (field, document) where the document disagrees with the property."""
    facts = list(document_facts)
    findings: list[Finding] = []
    for check in CHECKS:
        listed = _property_evidence(prop, check.document_field)
        if listed.value is None:
            continue
        for fact in facts:
            doc = fact.evidence
            if fact.name != check.document_field or doc.value is None:
                continue
            if not _differs(check.document_field, listed.value, doc.value):
                continue
            ocr = (
                " The document value was read by OCR, so it may be a misreading."
                if doc.status is Status.uncertain
                else ""
            )
            findings.append(
                Finding(
                    id=f"{prop.id}:{profile.id}:{RULE_ID}:{check.document_field}:{doc.source}",
                    rule_id=RULE_ID,
                    category=check.category,
                    outcome=Outcome.concern,
                    title=f"Documents disagree on the {check.label}",
                    reason=(
                        f"The listing gives the {check.label} as "
                        f"{_show(check.document_field, listed.value)} ({listed.source}), but "
                        f"{doc.source} says {_show(check.document_field, doc.value)}.{ocr}"
                    ),
                    facts=[
                        CitedFact(
                            name=f"listed_{check.document_field}", evidence=listed.model_dump()
                        ),
                        CitedFact(name=f"document_{check.document_field}", evidence=doc),
                    ],
                    next_step=f"Ask the landlord which {check.label} is correct, and get it "
                    "in writing before signing.",
                )
            )
    return findings
