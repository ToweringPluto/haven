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


# --- Signed-in features -------------------------------------------------------------------


def current_user_examples() -> dict[str, Json]:
    return {
        "signed_in": {
            "summary": "Illustrative signed-in user",
            "value": {"sub": "auth0|illustrative-user-0001", "email": "renter@example.com"},
        }
    }


def photo_screen_examples() -> dict[str, Json]:
    """The persona upload fixtures' screening output, reshaped: a screened photo is never
    stored, so it has no upload id."""
    out: dict[str, Json] = {}
    for p in PERSONAS:
        upload = load(p, "upload")
        if upload["kind"] != "photo":
            continue
        signals = [{**s, "upload_id": None} for s in upload["signals"]]
        out[p] = {
            "summary": SUMMARIES[p],
            "value": {"evidence_quality": upload["evidence_quality"], "signals": signals},
        }
    return out


def read_aloud_examples() -> dict[str, Json]:
    return {
        "report_sentence": {
            "summary": "A report sentence",
            "value": {
                "text": "The estimated monthly cost is within your stated budget, but check "
                "the entrance before signing."
            },
        }
    }
