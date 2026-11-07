"""Rule registry: transparent checks over property facts, renter needs and location data.

Each rule is a function ``evaluate(prop, profile, location, cost) -> Finding`` registered
with :func:`rule`, plus an ``applies_to(profile)`` predicate. :func:`evaluate_rules` runs
every rule that applies, in registration order. Rules never invent data: anything they
can't check comes back ``unknown`` with a ``next_step``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from haven.domain import (
    CitedFact,
    CostBreakdown,
    Evidence,
    FindingCategory,
    Origin,
    Outcome,
    Property,
    RenterProfile,
    Status,
)
from haven.domain.findings import Finding
from haven.location import LocationContext

type Evaluate = Callable[
    [Property, RenterProfile, LocationContext | None, CostBreakdown | None], Finding
]
type AppliesTo = Callable[[RenterProfile], bool]


@dataclass(frozen=True)
class Rule:
    rule_id: str
    category: FindingCategory
    title: str
    applies_to: AppliesTo
    evaluate: Evaluate


REGISTRY: dict[str, Rule] = {}


def always(_: RenterProfile) -> bool:
    return True


def rule(
    rule_id: str, *, category: FindingCategory, title: str, applies_to: AppliesTo = always
) -> Callable[[Evaluate], Evaluate]:
    """Register ``evaluate`` as rule ``rule_id``."""

    def register(evaluate: Evaluate) -> Evaluate:
        if rule_id in REGISTRY:
            raise ValueError(f"rule {rule_id!r} is already registered")
        REGISTRY[rule_id] = Rule(rule_id, category, title, applies_to, evaluate)
        return evaluate

    return register


def finding(
    rule_id: str,
    prop: Property,
    profile: RenterProfile,
    outcome: Outcome,
    reason: str,
    *,
    facts: list[CitedFact] | None = None,
    next_step: str | None = None,
) -> Finding:
    registered = REGISTRY[rule_id]
    return Finding(
        id=f"{prop.id}:{profile.id}:{rule_id}",
        rule_id=rule_id,
        category=registered.category,
        outcome=outcome,
        title=registered.title,
        reason=reason,
        facts=facts or [],
        next_step=next_step,
    )


def fact(name: str, evidence: Evidence[Any]) -> CitedFact:
    """Cite an Evidence value of any scalar type."""
    return CitedFact(name=name, evidence=evidence.model_dump())


def user_fact(name: str, value: Any) -> CitedFact:
    """Cite something the renter stated in their profile."""
    return CitedFact(
        name=name,
        evidence={
            "value": value,
            "origin": Origin.user,
            "source": "Renter profile",
            "status": Status.known,
        },
    )


def evaluate_rules(
    prop: Property,
    profile: RenterProfile,
    location: LocationContext | None,
    cost: CostBreakdown | None,
) -> list[Finding]:
    """Findings of every registered rule that applies to ``profile``."""
    return [
        r.evaluate(prop, profile, location, cost)
        for r in REGISTRY.values()
        if r.applies_to(profile)
    ]
