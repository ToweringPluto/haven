"""Plain-language explanation: wording rules, report sections and optional Gemini rewording."""

from haven.explain.language import BANNED_CERTAINTY_PHRASES, certainty_phrases
from haven.explain.report import HEADINGS, build_sections

__all__ = ["BANNED_CERTAINTY_PHRASES", "HEADINGS", "build_sections", "certainty_phrases"]
