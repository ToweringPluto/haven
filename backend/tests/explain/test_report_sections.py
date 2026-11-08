"""Template report sections and the optional Gemini rewording guard."""

from typing import Any

import pytest

from haven.domain import (
    EvidenceQuality,
    Finding,
    FindingCategory,
    Likelihood,
    Outcome,
    ReportSection,
    Signal,
    SignalKind,
)
from haven.explain import HEADINGS, build_sections, certainty_phrases
from haven.explain.gemini_wording import reword_sections
from haven.gemini import GeminiError


def finding(fid: str, outcome: Outcome, category: FindingCategory, reason: str) -> Finding:
    return Finding(
        id=fid,
        rule_id=fid,
        category=category,
        outcome=outcome,
        title=fid,
        reason=reason,
        next_step=None if outcome is Outcome.meets else f"Ask about {fid}",
    )


FINDINGS = [
    finding("budget", Outcome.concern, FindingCategory.cost, "Estimated total £1,504 a month"),
    finding("band", Outcome.meets, FindingCategory.missing_info, "The listing states band C"),
    finding("steps", Outcome.concern, FindingCategory.access, "4 steps at the entrance"),
    finding("lift", Outcome.unknown, FindingCategory.access, "Lift not stated"),
]
SIGNALS = [
    Signal(
        id="u:possible_mould",
        kind=SignalKind.possible_mould,
        likelihood=Likelihood.possible,
        evidence_quality=EvidenceQuality.good,
        source="Gemini (test)",
        note="Look for black spots around windows.",
    ),
    Signal(
        id="u:possible_damp",
        kind=SignalKind.possible_damp,
        likelihood=Likelihood.unlikely,
        evidence_quality=EvidenceQuality.good,
        source="Gemini (test)",
    ),
]


def by_heading(sections: list[ReportSection]) -> dict[str, list[tuple[str, list[str]]]]:
    return {s.heading: [(x.text, x.cites) for x in s.sentences] for s in sections}


def test_sections_sort_findings_and_signals() -> None:
    sections = build_sections(FINDINGS, SIGNALS)
    assert [s.heading for s in sections] == list(HEADINGS)
    got = by_heading(sections)
    assert got["What works"] == [("The listing states band C.", ["band"])]
    assert got["What could be expensive"] == [("Estimated total £1,504 a month.", ["budget"])]
    unsuitable = got["What may be unsuitable"]
    assert ("4 steps at the entrance.", ["steps"]) in unsuitable
    assert any(cites == ["u:possible_mould"] for _, cites in unsuitable)
    check = got["Check before signing"]
    assert ("Lift not stated.", ["lift"]) in check
    assert ("Ask about lift.", ["lift"]) in check
    assert ("Ask about budget.", ["budget"]) in check
    assert ("Look for black spots around windows.", ["u:possible_mould"]) in check
    # an "unlikely" signal says nothing
    assert all("u:possible_damp" not in c for s in sections for _, c in by_heading([s])[s.heading])
    for section in sections:
        for sentence in section.sentences:
            assert certainty_phrases(sentence.text) == []


def test_empty_sections_are_kept() -> None:
    sections = build_sections([], [])
    assert [s.heading for s in sections] == list(HEADINGS)
    assert all(s.sentences == [] for s in sections)


class FakeWording:
    model = "gemini-test"

    def __init__(self, answer: Any = None, error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error

    def generate_json(
        self, *, prompt: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None
    ) -> Any:
        if self.error:
            raise self.error
        return self.answer(prompt) if callable(self.answer) else self.answer


def sentences(sections: list[ReportSection]) -> list[str]:
    return [x.text for s in sections for x in s.sentences]


def rewordings(transform: Any) -> Any:
    def answer(_: str) -> dict[str, Any]:
        base = sentences(build_sections(FINDINGS, SIGNALS))
        return {"sentences": [{"i": i, "text": transform(t)} for i, t in enumerate(base)]}

    return answer


def test_good_rewording_is_used_and_keeps_cites() -> None:
    template = build_sections(FINDINGS, SIGNALS)
    reworded = reword_sections(template, FakeWording(rewordings(lambda t: "Note: " + t)))
    assert sentences(reworded) == ["Note: " + t for t in sentences(template)]
    assert [[x.cites for x in s.sentences] for s in reworded] == [
        [x.cites for x in s.sentences] for s in template
    ]


@pytest.mark.parametrize(
    "model",
    [
        FakeWording(error=GeminiError("down")),
        FakeWording({"sentences": []}),
        FakeWording("nonsense"),
        FakeWording(rewordings(lambda t: t + " The flat definitely has damp.")),
        FakeWording(rewordings(lambda t: "".join(c for c in t if not c.isdigit()) or "x")),
        FakeWording(rewordings(lambda t: t * 5)),
    ],
    ids=["error", "missing", "not-json", "certainty", "dropped-number", "too-long"],
)
def test_bad_rewording_keeps_the_template(model: FakeWording) -> None:
    template = build_sections(FINDINGS, SIGNALS)
    assert reword_sections(template, model) == template
