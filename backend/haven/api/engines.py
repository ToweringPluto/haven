"""``EngineBackend``: real engines for every endpoint, plus the illustrative persona fixtures.

* ``POST /v1/properties/{id}/cost`` → :func:`haven.cost.estimate_monthly_cost` (including the
  Lothian rent and Local Housing Allowance context).
* ``POST /v1/properties/{id}/suitability`` → the location cache + cost engine + rules
  (:func:`haven.rules.evaluate_rules`). Properties without cached location data get
  ``unknown`` location findings, never "fine".
* ``POST /v1/uploads`` / ``DELETE /v1/uploads/{id}`` → :class:`haven.store.UploadStore`
  (files on disk under ``Settings.upload_dir``, type sniffed from magic bytes, image
  metadata stripped). Photos are screened (quality gate, then the configured screener:
  Gemini or none); floor plans get a quality grade; documents have their facts extracted.
* ``POST /v1/photo-screen`` → the same screening pipeline, in memory only.
* ``POST /v1/assessments`` → cost + rule findings + document conflicts + upload signals, with
  sections from :func:`haven.explain.build_sections` (optionally reworded by Gemini). The
  persona pairs (with no uploads of their own) still return their illustrative reports, so
  the contract examples stay valid.
* Profiles, reports, upload records and saved homes are saved through a
  :class:`haven.store.RecordStore` (Tiger Cloud when ``HAVEN_DATABASE_URL`` is set, memory
  otherwise), each owned by the signed-in user who created it.
* ``GET /v1/properties`` / ``GET /v1/properties/{id}`` serve the seed properties
  (``data/seed/properties.yaml``, fictional and marked illustrative) first, then the persona
  fixture properties. Renters can't add listings.

Read-aloud still has no speech service (501).
"""

import io
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from haven.api.errors import PayloadTooLarge, ServiceUnavailable, UnsupportedMediaType
from haven.api.fixtures import FixtureBackend
from haven.api.schemas import AssessmentRequest, PhotoScreen
from haven.config import UPLOAD_DIR, UPLOAD_MAX_BYTES, Settings
from haven.cost import CostReferences, estimate_monthly_cost, load_cost_references
from haven.domain import (
    CitedFact,
    CostBreakdown,
    Finding,
    Property,
    RenterProfile,
    Report,
    Signal,
    SuitabilityAssessment,
    Upload,
    UploadKind,
)
from haven.explain import build_sections
from haven.explain.gemini_wording import reword_sections
from haven.gemini import GeminiError, JsonModel, make_gemini
from haven.location import CachedProvider
from haven.rules import evaluate_rules, location_for
from haven.rules.conflicts import conflict_findings
from haven.screening import (
    QualityReport,
    Screener,
    ScreeningPipeline,
    ScreeningResult,
    assess_quality,
    make_screener,
)
from haven.screening.documents import extract_document
from haven.screening.screeners import SIGNAL_KINDS, insufficient
from haven.store import (
    MemoryRecordStore,
    RecordStore,
    SeedStore,
    UploadRejected,
    UploadStore,
    load_seed,
)

logger = logging.getLogger(__name__)

_IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class EngineBackend(FixtureBackend):
    def __init__(
        self,
        directory: Path,
        *,
        today: Callable[[], date] = date.today,
        references: Callable[[], CostReferences] = load_cost_references,
        seed: SeedStore | None = None,
        location: CachedProvider | None = None,
        uploads: UploadStore | None = None,
        records: RecordStore | None = None,
        settings: Settings | None = None,
        screener: Screener | None = None,
        wording_model: JsonModel | None = None,
    ) -> None:
        super().__init__(directory)
        self.settings = Settings() if settings is None else settings
        self._today = today
        self.location = CachedProvider() if location is None else location
        self.uploads = (
            UploadStore(UPLOAD_DIR, max_bytes=UPLOAD_MAX_BYTES) if uploads is None else uploads
        )
        self.records: RecordStore = MemoryRecordStore() if records is None else records
        self.screener = make_screener(self.settings) if screener is None else screener
        if wording_model is None and self.settings.report_wording == "gemini":
            wording_model = make_gemini(self.settings)
        self.wording_model = wording_model
        self._references = references
        self.seed = load_seed() if seed is None else seed
        clash = {p.id for p in self.seed} & self._properties.keys()
        if clash:
            raise ValueError(f"seed property ids clash with fixture ids: {sorted(clash)}")
        self._properties = {**{p.id: p for p in self.seed}, **self._properties}
        self._fixture_upload_ids = set(self._uploads)

    # --- engines -----------------------------------------------------------------------

    def _cost(self, prop: Property, profile: RenterProfile | None) -> CostBreakdown:
        return estimate_monthly_cost(prop, profile, on=self._today(), references=self._references())

    def _findings(
        self, prop: Property, profile: RenterProfile, cost: CostBreakdown
    ) -> list[Finding]:
        location = location_for(self.location, prop, profile)
        return evaluate_rules(prop, profile, location, cost)

    def estimate_cost(self, property_id: str, profile_id: str | None) -> CostBreakdown:
        prop = self.get_property(property_id)
        profile = None if profile_id is None else self.get_profile(profile_id)
        return self._cost(prop, profile)

    def assess_suitability(self, property_id: str, profile_id: str) -> SuitabilityAssessment:
        prop = self.get_property(property_id)
        profile = self.get_profile(profile_id)
        return SuitabilityAssessment(
            property_id=prop.id,
            profile_id=profile.id,
            findings=self._findings(prop, profile, self._cost(prop, profile)),
        )

    # --- screening ---------------------------------------------------------------------

    def _pipeline(self, screener: Screener | None = None) -> ScreeningPipeline:
        return ScreeningPipeline(screener or self.screener, self.settings.quality)

    def _screen_upload_image(self, content: bytes, upload_id: str) -> ScreeningResult | None:
        """Screen a stored photo. A screener failure means "can't tell", never a failed upload."""
        try:
            return self._pipeline().run(content, upload_id=upload_id)
        except GeminiError as exc:
            logger.warning("Photo screening failed for an upload: %s", exc)
            fallback = _UnavailableScreener(str(exc))
            return self._pipeline(fallback).run(content, upload_id=upload_id)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            logger.info("Couldn't screen an upload: %s", type(exc).__name__)
            return None

    def screen_photo(self, *, content: bytes, content_type: str) -> PhotoScreen:
        try:
            result = self._pipeline().run(content)
        except GeminiError as exc:
            raise ServiceUnavailable(
                "Photo screening is temporarily unavailable. Try again shortly."
            ) from exc
        except (UnidentifiedImageError, OSError) as exc:
            raise UnsupportedMediaType("The image couldn't be read.") from exc
        return PhotoScreen(evidence_quality=result.quality.quality, signals=result.signals)

    # --- uploads -----------------------------------------------------------------------

    def create_upload(
        self,
        *,
        kind: UploadKind,
        filename: str,
        content_type: str,
        content: bytes,
        property_id: str | None,
        owner_sub: str,
    ) -> Upload:
        # content_type is the client's claim; the store decides the type from the bytes.
        if property_id is not None:
            self.get_property(property_id)
        try:
            upload = self.uploads.save(
                kind=kind, filename=filename, content=content, property_id=property_id
            )
        except UploadRejected as exc:
            if exc.reason == "too_large":
                raise PayloadTooLarge(str(exc)) from exc
            raise UnsupportedMediaType(str(exc)) from exc

        upload = self._screen(upload, content)
        self.uploads.update(upload)
        self.records.put("upload", upload, owner_sub=owner_sub)
        return upload

    def _forget_upload_file(self, upload_id: str) -> None:
        self.uploads.delete(upload_id)

    def _screen(self, upload: Upload, content: bytes) -> Upload:
        is_image = upload.content_type in _IMAGE_TYPES
        if upload.kind is UploadKind.document or not is_image:
            extraction = extract_document(
                content, filename=upload.filename, content_type=upload.content_type
            )
            return upload.model_copy(update={"extracted_facts": extraction.facts})
        if upload.kind is UploadKind.photo:
            result = self._screen_upload_image(content, upload.id)
            if result is None:
                return upload
            return upload.model_copy(
                update={"evidence_quality": result.quality.quality, "signals": result.signals}
            )
        # Floor plan: a quality grade only; the photo signals don't apply to drawings.
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                report = assess_quality(image, self.settings.quality)
        except (UnidentifiedImageError, OSError, ValueError):
            return upload
        return upload.model_copy(update={"evidence_quality": report.quality})

    # --- reports -----------------------------------------------------------------------

    def create_assessment(self, data: AssessmentRequest, owner_sub: str) -> Report:
        profile = self._usable_profile(data.profile_id, owner_sub)
        prop = self.get_property(data.property_id)
        uploads = [self._get_upload(upload_id, owner_sub) for upload_id in data.upload_ids]

        persona = self._by_property.get(prop.id)
        if (
            persona is not None
            and persona.profile.id == profile.id
            and set(data.upload_ids) <= self._fixture_upload_ids
        ):
            return super().create_assessment(data, owner_sub)  # the illustrative example

        cost = self._cost(prop, profile)
        facts: list[CitedFact] = [f for u in uploads for f in u.extracted_facts]
        findings = self._findings(prop, profile, cost) + conflict_findings(prop, profile, facts)
        signals: list[Signal] = [s for u in uploads for s in u.signals]
        sections = build_sections(findings, signals)
        if self.wording_model is not None:
            sections = reword_sections(sections, self.wording_model)
        report = Report(
            id=_new_id("report"),
            created_at=datetime.now(UTC),
            illustrative=prop.illustrative,
            profile=profile,
            property=prop,
            cost=cost,
            findings=findings,
            signals=signals,
            sections=sections,
        )
        self.records.put("report", report, owner_sub=owner_sub)
        return report


class _UnavailableScreener:
    """Stands in when the configured screener fails: every signal is insufficient."""

    def __init__(self, why: str) -> None:
        self.why = why
        self.name = "Haven (photo screening unavailable)"

    def screen(
        self, image: Image.Image, *, quality: QualityReport, upload_id: str | None
    ) -> list[Signal]:
        return [
            insufficient(
                kind,
                quality=quality.quality,
                upload_id=upload_id,
                source=self.name,
                why=f"Photo screening wasn't available when this was uploaded ({self.why}).",
            )
            for kind in SIGNAL_KINDS
        ]
