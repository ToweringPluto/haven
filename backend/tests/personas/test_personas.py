"""Persona regression: the rules engine on seed properties must give the recorded outcomes.

Each ``tests/personas/<persona>.yaml`` names a persona profile (from
``contracts/examples/<persona>/profile.json``) and, per seed property, the expected
``rule_id -> outcome`` for every rule that applies. The run uses the committed location
cache and the cost engine on a fixed date, so it is offline and deterministic.

If a change to rules or data moves an outcome on purpose, update the YAML in the same
commit and say why in the commit message.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from haven.config import CONTRACT_EXAMPLES_DIR
from haven.cost import estimate_monthly_cost
from haven.domain import Outcome, Property, RenterProfile
from haven.location import CachedProvider, Point
from haven.rules import evaluate_rules
from haven.store import load_seed

HERE = Path(__file__).resolve().parent
ON = date(2026, 11, 7)  # inside the price cap and council tax data on file
RADIUS_M = 1500.0


def load_profile(persona: str) -> RenterProfile:
    path = CONTRACT_EXAMPLES_DIR / persona / "profile.json"
    return RenterProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def outcomes(prop: Property, profile: RenterProfile) -> dict[str, Outcome]:
    destinations = [
        Point(latitude=d.latitude, longitude=d.longitude, name=d.name) for d in profile.destinations
    ]
    location = CachedProvider().context(prop, radius_m=RADIUS_M, destinations=destinations)
    cost = estimate_monthly_cost(prop, profile, on=ON)
    return {f.rule_id: f.outcome for f in evaluate_rules(prop, profile, location, cost)}


def cases() -> list[Any]:
    params = []
    for path in sorted(HERE.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        for property_id, expected in spec["expected"].items():
            params.append(
                pytest.param(
                    spec["persona"], property_id, expected, id=f"{path.stem}-{property_id}"
                )
            )
    return params


@pytest.mark.parametrize(("persona", "property_id", "expected"), cases())
def test_persona_outcomes(persona: str, property_id: str, expected: dict[str, str]) -> None:
    prop = load_seed().get(property_id)
    assert prop is not None, property_id
    actual = {rule_id: o.value for rule_id, o in outcomes(prop, load_profile(persona)).items()}
    assert actual == expected


def test_coverage_of_personas_and_properties() -> None:
    specs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in HERE.glob("*.yaml")]
    assert len(specs) >= 3
    for spec in specs:
        assert len(spec["expected"]) >= 6, spec["persona"]
