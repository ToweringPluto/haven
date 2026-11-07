"""OpenAPI examples, taken from the committed contract examples in ``contracts/examples``.

These always come from the repo's contract files (not ``HAVEN_FIXTURES_DIR``), so the
documented examples are the same whichever backend serves the API.
"""

import json
from functools import cache
from typing import Any

from haven.api.fixtures import PERSONAS
from haven.config import CONTRACT_EXAMPLES_DIR

type Json = dict[str, Any]

SUMMARIES = {
    "wheelchair_user": "Wheelchair user (illustrative persona)",
    "student": "Student (illustrative persona)",
    "tight_budget": "Renter on a tight budget (illustrative persona)",
}


@cache
def _load(persona: str, stem: str) -> Json:
    data: Json = json.loads(
        (CONTRACT_EXAMPLES_DIR / persona / f"{stem}.json").read_text(encoding="utf-8")
    )
    return data


def load(persona: str, stem: str) -> Json:
    """A fresh copy of one contract example."""
    copied: Json = json.loads(json.dumps(_load(persona, stem)))
    return copied


def per_persona(stem: str) -> dict[str, Json]:
    """OpenAPI ``examples`` map: one named example per persona."""
    return {p: {"summary": SUMMARIES[p], "value": load(p, stem)} for p in PERSONAS}


def without_id(data: Json) -> Json:
    return {k: v for k, v in data.items() if k != "id"}


def profile_list() -> Json:
    return {"items": [load(p, "profile") for p in PERSONAS]}


def property_list() -> Json:
    return {"items": [item for p in PERSONAS for item in load(p, "properties")["items"]]}


def property_examples() -> dict[str, Json]:
    return {
        p: {"summary": SUMMARIES[p], "value": load(p, "properties")["items"][0]} for p in PERSONAS
    }


def profile_inputs() -> dict[str, Json]:
    return {p: {"summary": SUMMARIES[p], "value": without_id(load(p, "profile"))} for p in PERSONAS}


def property_inputs() -> dict[str, Json]:
    return {
        p: {"summary": SUMMARIES[p], "value": without_id(load(p, "properties")["items"][0])}
        for p in PERSONAS
    }


def single(value: Json, summary: str = "Illustrative example") -> dict[str, Json]:
    return {"example": {"summary": summary, "value": value}}


def json_response(status: int, examples: dict[str, Json]) -> dict[int | str, Json]:
    """``responses=`` entry adding named examples to a JSON success response."""
    return {status: {"content": {"application/json": {"examples": examples}}}}
