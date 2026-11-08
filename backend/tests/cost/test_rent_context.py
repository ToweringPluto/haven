"""Rent context: Lothian rent statistics and LHA next to the listing's rent."""

from datetime import date

import pytest

from haven.cost import load_cost_references
from haven.cost.engine import rent_context
from haven.domain import Evidence, Origin, Property, RentComparison, Status
from haven.store import load_seed

ON = date(2026, 11, 7)


def seed_property() -> Property:
    return next(iter(load_seed()))


def with_(prop: Property, *, rent: float | None = None, bedrooms: int | None = 2) -> Property:
    def ev(value: object) -> Evidence[object]:
        status = Status.insufficient if value is None else Status.known
        return Evidence(value=value, origin=Origin.listing, source="test", status=status)

    return prop.model_copy(update={"rent_pcm_gbp": ev(rent), "bedrooms": ev(bedrooms)})


def test_compares_with_median_and_lha() -> None:
    refs = load_cost_references()
    assert refs.rents is not None and refs.lha is not None
    median = refs.rents.rents.bedrooms_2.median_gbp_pcm
    lha = refs.lha.monthly_gbp_by_bedrooms[2]

    context = rent_context(with_(seed_property(), rent=median), refs, ON)
    assert context is not None
    assert context.median_gbp_pcm == median
    assert context.rent_vs_median is RentComparison.similar
    assert context.lha_monthly_gbp == lha
    assert context.rent_vs_lha is RentComparison.above
    assert any("Lothian" in c for c in context.caveats)

    low = rent_context(with_(seed_property(), rent=lha * 0.5), refs, ON)
    assert low is not None and low.rent_vs_median is RentComparison.below
    assert low.rent_vs_lha is RentComparison.below


@pytest.mark.parametrize("bedrooms", [0, 5, None])
def test_unpublished_sizes_have_no_context(bedrooms: int | None) -> None:
    assert (
        rent_context(
            with_(seed_property(), rent=900, bedrooms=bedrooms), load_cost_references(), ON
        )
        is None
    )


def test_unknown_rent_still_shows_the_figures() -> None:
    context = rent_context(with_(seed_property(), rent=None), load_cost_references(), ON)
    assert context is not None
    assert context.rent_vs_median is None and context.rent_vs_lha is None


def test_lha_is_left_out_outside_its_year() -> None:
    context = rent_context(
        with_(seed_property(), rent=1000), load_cost_references(), date(2027, 6, 1)
    )
    assert context is not None
    assert context.lha_monthly_gbp is None and context.rent_vs_lha is None
    assert not any("Housing Allowance" in c for c in context.caveats)
