"""``EngineBackend``: real engines where they exist, fixtures everywhere else.

Endpoints move from the fixture backend to an engine one at a time. So far:

* ``POST /v1/properties/{id}/cost`` → :func:`haven.cost.estimate_monthly_cost`.

Profiles and properties still come from the persona fixtures (plus anything created through
the API) until the seed store lands (P2-01).
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from haven.api.fixtures import FixtureBackend
from haven.cost import CostReferences, estimate_monthly_cost, load_cost_references
from haven.domain import CostBreakdown


class EngineBackend(FixtureBackend):
    def __init__(
        self,
        directory: Path,
        *,
        today: Callable[[], date] = date.today,
        references: Callable[[], CostReferences] = load_cost_references,
    ) -> None:
        super().__init__(directory)
        self._today = today
        self._references = references

    def estimate_cost(self, property_id: str, profile_id: str | None) -> CostBreakdown:
        prop = self.get_property(property_id)
        profile = None if profile_id is None else self.get_profile(profile_id)
        return estimate_monthly_cost(prop, profile, on=self._today(), references=self._references())
