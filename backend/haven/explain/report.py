"""Report sections built from findings and signals, with no model involved.

Every sentence is taken from a finding's own ``reason`` / ``next_step`` or a signal's note, and
cites the id it came from, so nothing appears in a report that the evidence doesn't say. The
four headings match the illustrative reports in ``contracts/examples``:

* **What works**: findings that meet the renter's requirements.
* **What may be unsuitable**: access, location and condition concerns, and photo signals
  rated ``possible`` or ``likely``.
* **What could be expensive**: cost concerns (including documents that disagree with the
  listing on rent, council tax band or EPC rating).
* **Check before signing**: the next step for every concern and unknown, and what to check
  for each photo signal.

There is deliberately no overall score or verdict.
"""

from collections.abc import Sequence

from haven.domain import (
    Finding,
    FindingCategory,
    Likelihood,
    Outcome,
    ReportSection,
    ReportSentence,
    Signal,
    SignalKind,
)

WORKS = "What works"
UNSUITABLE = "What may be unsuitable"
EXPENSIVE = "What could be expensive"
CHECK = "Check before signing"
HEADINGS = (WORKS, UNSUITABLE, EXPENSIVE, CHECK)

_SIGNAL_PHRASES = {
    SignalKind.possible_damp: "signs of damp",
    SignalKind.possible_mould: "signs of mould",
    SignalKind.entrance_step: "a step at the entrance",
}

_FLAGGED = (Likelihood.possible, Likelihood.likely)


def _sentence(text: str, *cites: str) -> ReportSentence:
    text = " ".join(text.split())
    if text and not text.endswith((".", "!", "?")):
        text += "."
    return ReportSentence(text=text, cites=list(cites))


def _signal_sentence(signal: Signal) -> ReportSentence:
    phrase = _SIGNAL_PHRASES[signal.kind]
    how = "likely" if signal.likelihood is Likelihood.likely else "possible"
    return _sentence(
        f"An uploaded photo may show {phrase} (rated {how} by {signal.source}); this is a "
        "possibility to check in person",
        signal.id,
    )


def build_sections(findings: Sequence[Finding], signals: Sequence[Signal]) -> list[ReportSection]:
    """The four report sections, in order. Sections with nothing to say are kept empty."""
    sections: dict[str, list[ReportSentence]] = {heading: [] for heading in HEADINGS}
    for finding in findings:
        if finding.outcome is Outcome.meets:
            sections[WORKS].append(_sentence(finding.reason, finding.id))
            continue
        if finding.outcome is Outcome.concern:
            if finding.category is FindingCategory.cost:
                sections[EXPENSIVE].append(_sentence(finding.reason, finding.id))
            elif finding.category is not FindingCategory.missing_info:
                sections[UNSUITABLE].append(_sentence(finding.reason, finding.id))
            else:
                sections[CHECK].append(_sentence(finding.reason, finding.id))
        else:  # unknown: say why it's unknown before what to do about it
            sections[CHECK].append(_sentence(finding.reason, finding.id))
        if finding.next_step:
            sections[CHECK].append(_sentence(finding.next_step, finding.id))

    for signal in signals:
        if signal.likelihood not in _FLAGGED:
            continue
        sections[UNSUITABLE].append(_signal_sentence(signal))
        if signal.note:
            sections[CHECK].append(_sentence(signal.note, signal.id))

    return [ReportSection(heading=h, sentences=sections[h]) for h in HEADINGS]
