from datetime import UTC, date, datetime
from typing import Any

import pytest

from haven.domain import (
    BudgetComparison,
    CostBreakdown,
    CostKind,
    CostLine,
    EpcBand,
    Evidence,
    MainFuel,
    Origin,
    Property,
    PropertyType,
    RenterProfile,
    Report,
    Status,
)


def listing(value: object) -> dict[str, Any]:
    """Evidence payload; pydantic validates it against each field's own Evidence[T]."""
    return {"value": value, "origin": Origin.listing, "source": "listing", "status": Status.known}


def missing() -> dict[str, Any]:
    return {"value": None, "origin": Origin.listing, "source": "listing", "status": "insufficient"}


@pytest.fixture
def prop() -> Property:
    return Property(
        id="p1",
        title="Illustrative property",
        illustrative=True,
        area="Leith",
        rent_pcm_gbp=listing(1000.0),
        bedrooms=listing(1),
        property_type=listing(PropertyType.flat),
        floor_area_m2=listing(50.0),
        council_tax_band=missing(),
        epc_rating=listing(EpcBand.D),
        main_fuel=listing(MainFuel.mains_gas),
        floor_level=listing(2),
        has_lift=missing(),
        entrance_steps=listing(3),
    )


@pytest.fixture
def report(prop: Property) -> Report:
    rent = CostLine(kind=CostKind.rent, label="Rent", monthly_gbp=listing(1000.0))
    total = Evidence[float](
        value=None,
        origin=Origin.estimate,
        source="haven cost engine",
        as_of=date(2026, 11, 7),
        status=Status.insufficient,
    )
    cost = CostBreakdown(
        property_id="p1",
        lines=[rent],
        total_monthly_gbp=total,
        budget_monthly_gbp=1200.0,
        budget_comparison=BudgetComparison.unknown,
    )
    return Report(
        id="r1",
        created_at=datetime(2026, 11, 7, tzinfo=UTC),
        profile=RenterProfile(id="u1", label="Student"),
        property=prop,
        cost=cost,
    )
