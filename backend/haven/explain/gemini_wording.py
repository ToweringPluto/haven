"""Optional Gemini rewording of the template report sentences (``HAVEN_REPORT_WORDING=gemini``).

Gemini only rewrites the *wording* of sentences that :func:`haven.explain.report.build_sections`
already built from the evidence. It never adds or removes sentences, and never sees or
changes what a sentence cites: the cites are copied from the template by position.

The whole rewording is rejected (and the template kept) when:

* the call fails or the answer isn't the expected JSON;
* a sentence is missing, extra, empty or far longer than the original;
* any reworded sentence uses certainty wording (:func:`haven.explain.certainty_phrases`);
* a reworded sentence drops a number (e.g. a rent or a minute count) the original stated.
"""

import json
import logging
import re
from typing import Any

from haven.domain import ReportSection, ReportSentence
from haven.explain.language import certainty_phrases
from haven.gemini import GeminiError, JsonModel

logger = logging.getLogger(__name__)

MAX_GROWTH = 2.0  # a reworded sentence may be at most twice as long as the original
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

PROMPT = (
    "Reword each sentence below from a rental property report so it reads naturally and "
    "plainly to a renter in the UK. Rules: keep every fact and number exactly; don't add facts, "
    "advice or opinions; don't merge or split sentences; keep possibilities as possibilities "
    "(never say a property has damp or mould, is accessible, is safe, or anything is "
    "confirmed or guaranteed). Return the same 'i' for each sentence.\n\nSentences (JSON):\n"
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"i": {"type": "integer"}, "text": {"type": "string"}},
                "required": ["i", "text"],
            },
        }
    },
    "required": ["sentences"],
}


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


def _acceptable(original: str, reworded: object) -> bool:
    if not isinstance(reworded, str) or not reworded.strip():
        return False
    if len(reworded) > MAX_GROWTH * max(len(original), 40):
        return False
    if certainty_phrases(reworded):
        return False
    return _numbers(original) <= _numbers(reworded)


def reword_sections(sections: list[ReportSection], model: JsonModel) -> list[ReportSection]:
    """``sections`` with Gemini's wording, or ``sections`` unchanged if it's rejected."""
    originals = [s for section in sections for s in section.sentences]
    if not originals:
        return sections
    payload = [{"i": i, "text": s.text} for i, s in enumerate(originals)]
    try:
        answer = model.generate_json(
            prompt=PROMPT + json.dumps(payload, ensure_ascii=False), schema=SCHEMA
        )
    except GeminiError as exc:
        logger.info("Keeping template report wording: %s", exc)
        return sections

    items = answer.get("sentences") if isinstance(answer, dict) else None
    if not isinstance(items, list):
        return sections
    texts: dict[int, object] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("i"), int):
            texts[item["i"]] = item.get("text")
    if sorted(texts) != list(range(len(originals))):
        logger.info("Keeping template report wording: sentence count changed")
        return sections
    if not all(_acceptable(s.text, texts[i]) for i, s in enumerate(originals)):
        logger.info("Keeping template report wording: a reworded sentence was rejected")
        return sections

    reworded = iter(
        ReportSentence(text=" ".join(str(texts[i]).split()), cites=list(s.cites))
        for i, s in enumerate(originals)
    )
    return [
        ReportSection(
            heading=section.heading, sentences=[next(reworded) for _ in section.sentences]
        )
        for section in sections
    ]
