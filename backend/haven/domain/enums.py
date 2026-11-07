"""Enumerations shared across the Haven domain.

All enums are ``StrEnum`` so they serialise as plain strings in JSON and in the
exported OpenAPI contract.
"""

from enum import StrEnum


class Origin(StrEnum):
    """Where a value came from."""

    listing = "listing"
    public_data = "public_data"
    user = "user"
    model = "model"
    estimate = "estimate"


class Status(StrEnum):
    """How much a value can be relied on."""

    known = "known"
    estimated = "estimated"
    inferred = "inferred"
    uncertain = "uncertain"
    insufficient = "insufficient"


class Outcome(StrEnum):
    """Result of a single requirement check. ``unknown`` is not the same as ``concern``."""

    meets = "meets"
    concern = "concern"
    unknown = "unknown"


class Likelihood(StrEnum):
    """Screening signal strength. Always phrased as a possibility, never a diagnosis."""

    unlikely = "unlikely"
    possible = "possible"
    likely = "likely"
    insufficient_evidence = "insufficient_evidence"


class EvidenceQuality(StrEnum):
    """Quality of the uploaded evidence a signal was derived from."""

    good = "good"
    limited = "limited"
    poor = "poor"


class FindingCategory(StrEnum):
    cost = "cost"
    access = "access"
    location = "location"
    condition = "condition"
    missing_info = "missing_info"


class BudgetComparison(StrEnum):
    """Estimated monthly total compared with the renter's stated budget."""

    within = "within"
    over = "over"
    unknown = "unknown"


class CouncilTaxBand(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"


class EpcBand(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


class PropertyType(StrEnum):
    flat = "flat"
    maisonette = "maisonette"
    house = "house"
    bungalow = "bungalow"
    other = "other"


class MainFuel(StrEnum):
    mains_gas = "mains_gas"
    electricity = "electricity"
    other = "other"


class CostKind(StrEnum):
    rent = "rent"
    council_tax = "council_tax"
    energy = "energy"
    other = "other"


class SignalKind(StrEnum):
    """Scoped screening signals. Each is a *possible* feature to inspect."""

    possible_damp = "possible_damp"
    possible_mould = "possible_mould"
    entrance_step = "entrance_step"


class UploadKind(StrEnum):
    photo = "photo"
    floor_plan = "floor_plan"
    document = "document"


class Priority(StrEnum):
    """Renter priorities used to decide which checks apply and how they are ordered."""

    total_cost = "total_cost"
    step_free_access = "step_free_access"
    lift_access = "lift_access"
    transport_access = "transport_access"
    travel_time = "travel_time"
    heating_cost = "heating_cost"
    space = "space"
    nearby_schools = "nearby_schools"
    property_condition = "property_condition"
