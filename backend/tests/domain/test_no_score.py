"""Haven never aggregates into a single score: no schema field may look like one."""

import re
from typing import Any

from pydantic import BaseModel

from haven.domain import CostBreakdown, Finding, Property, RenterProfile, Report, Signal

SCORE_LIKE = re.compile(r"score|rating|grade|rank", re.IGNORECASE)
ALLOWED = {"epc_rating"}


def walk_schema(node: Any) -> list[str]:
    """Collect every property name in a JSON schema, including nested $defs."""
    names: list[str] = []
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            names.extend(props)
        for value in node.values():
            names.extend(walk_schema(value))
    elif isinstance(node, list):
        for value in node:
            names.extend(walk_schema(value))
    return names


def test_report_schema_has_no_score_fields() -> None:
    names = walk_schema(Report.model_json_schema())
    assert "epc_rating" in names  # sanity: the walk reaches nested models
    offending = sorted({n for n in names if SCORE_LIKE.search(n) and n not in ALLOWED})
    assert offending == []


def test_other_top_level_models_have_no_score_fields() -> None:
    models: list[type[BaseModel]] = [CostBreakdown, Finding, Signal, Property, RenterProfile]
    for model in models:
        names = walk_schema(model.model_json_schema())
        offending = {n for n in names if SCORE_LIKE.search(n) and n not in ALLOWED}
        assert not offending, f"{model.__name__}: {offending}"


def test_walk_detects_a_score_field() -> None:
    class Bad(BaseModel):
        overall_score: float

    class Wrapper(BaseModel):
        inner: Bad

    names = walk_schema(Wrapper.model_json_schema())
    assert any(SCORE_LIKE.search(n) for n in names)
