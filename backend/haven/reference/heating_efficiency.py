"""Typed schema for ``data/reference/heating_efficiency.yaml``.

The file holds **default seasonal efficiencies of heating systems** from SAP 10.2 (the UK
Government's Standard Assessment Procedure, 11-04-2023), Table 4a (heating systems) and Table 4b
(gas and liquid fuel boilers). It is produced by ``backend/scripts/ingest_heating_efficiency.py``
from the BRE PDF; never edit the figures by hand.

Why it's needed: the EPC model (``energy_kwh_per_m2_edinburgh.yaml``) gives *heat demand*.
The fuel a household buys is heat demand / efficiency (a 84%-efficient boiler buys about 1.19
kWh of gas per kWh of heat; a heat pump at 170% buys about 0.59 kWh of electricity).

What the figures are, and are not:

- They are SAP's **defaults** for when the actual product isn't known, not measurements of any
  property's system. A listing doesn't say which boiler or heaters a home has, so callers must
  treat the system as unknown: a ``central`` assumption plus the range ``lowest``-``highest``
  across the listed systems, and say so.
- For each fuel only systems in the RdSAP reduced data set ("rd" in the tables) are listed, as
  RdSAP is the method behind EPCs for existing homes. Heat pump rows that need evidence of a
  design flow temperature <= 35°C (SAP section 9.3) are left out: a listing gives no such
  evidence.
- ``space_efficiency_pct`` is the winter (space heating) efficiency; ``water_efficiency_pct`` is
  Table 4b's summer efficiency or Table 4a's water column where the table gives one. The EPC heat
  demand combines space and water heating, so callers using the space figure for both should note
  that hot water may be slightly underestimated.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from haven.domain import MainFuel
from haven.reference.loader import ReferenceDocument, load_reference

FILE_NAME = "heating_efficiency"


class HeatingSystem(BaseModel):
    """One SAP table row: a heating system and its default efficiency (in %)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    table: Literal["4a", "4b"]
    code: int = Field(ge=100, le=999, description="SAP heating system code.")
    group: str = Field(min_length=1, description="Table heading the row sits under.")
    description: str = Field(min_length=1)
    space_efficiency_pct: int = Field(gt=0, le=500)
    water_efficiency_pct: int | None = Field(default=None, gt=0, le=500)
    rdsap: Literal[True] = Field(description="Marked 'rd' (RdSAP reduced data set).")


class FuelEfficiency(BaseModel):
    """The systems considered for one heating fuel and the central assumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    central_pct: int = Field(gt=0, le=500)
    central_codes: list[int] = Field(min_length=1)
    central_label: str = Field(min_length=1, description="Short name of the assumed system.")
    central_basis: str = Field(min_length=1, description="Why this central figure.")
    systems: list[HeatingSystem] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Self:
        codes = [(s.table, s.code) for s in self.systems]
        if len(set(codes)) != len(codes):
            raise ValueError("duplicate system code")
        by_code = {s.code: s for s in self.systems}
        for code in self.central_codes:
            system = by_code.get(code)
            if system is None:
                raise ValueError(f"central code {code} is not among the systems")
            if system.space_efficiency_pct != self.central_pct:
                raise ValueError(f"central code {code} has a different efficiency")
        return self

    @property
    def lowest_pct(self) -> int:
        return min(s.space_efficiency_pct for s in self.systems)

    @property
    def highest_pct(self) -> int:
        return max(s.space_efficiency_pct for s in self.systems)

    def lowest_system(self) -> HeatingSystem:
        return min(self.systems, key=lambda s: (s.space_efficiency_pct, s.code))

    def highest_system(self) -> HeatingSystem:
        return max(self.systems, key=lambda s: (s.space_efficiency_pct, -s.code))


class HeatingEfficiencyReference(ReferenceDocument):
    """``heating_efficiency.yaml``: SAP 10.2 default heating efficiencies by fuel."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    publisher: Literal["BRE on behalf of BEIS"]
    document: Literal["SAP 10.2 (11-04-2023)"]
    source_url: str = Field(pattern=r"^https?://\S+$", description="SAP 10.2 PDF.")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="sha256 of the PDF.")
    selection: str = Field(min_length=1, description="Which table rows were taken, and why.")
    fuels: dict[MainFuel, FuelEfficiency]

    @model_validator(mode="after")
    def _check_fuels(self) -> Self:
        if set(self.fuels) != {MainFuel.mains_gas, MainFuel.electricity}:
            raise ValueError("expected exactly the mains_gas and electricity fuels")
        return self

    def for_fuel(self, fuel: MainFuel) -> FuelEfficiency | None:
        """Efficiencies for ``fuel``, or ``None`` when there is no figure (``MainFuel.other``)."""
        return self.fuels.get(fuel)


def load_heating_efficiency() -> HeatingEfficiencyReference:
    """Load the committed SAP heating efficiency reference file."""
    return load_reference(FILE_NAME, HeatingEfficiencyReference)
