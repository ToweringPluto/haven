"""``EngineBackend``: real engines where they exist, fixtures everywhere else.

Endpoints move from the fixture backend to an engine one at a time. So far:

* ``POST /v1/properties/{id}/cost`` → :func:`haven.cost.estimate_monthly_cost`.
* ``POST /v1/uploads`` / ``DELETE /v1/uploads/{id}`` → :class:`haven.store.UploadStore`
  (files on disk under ``Settings.upload_dir``, type sniffed from magic bytes, image
  metadata stripped). Screening comes later, so uploads still have no signals.
* ``POST /v1/properties/{id}/suitability`` → the location cache + cost engine + rules
  (:func:`haven.rules.evaluate_rules`). Properties without cached location data get
  ``unknown`` location findings, never "fine".
* ``GET /v1/properties`` / ``GET /v1/properties/{id}`` serve the seed properties
  (``data/seed/properties.yaml``, fictional and marked illustrative) first, then the persona
  fixture properties (still needed for the fixture suitability/assessment pairs), then
  anything created through the API.

Profiles still come from the persona fixtures (plus anything created through the API).
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from haven.api.errors import NotFound, PayloadTooLarge, UnsupportedMediaType
from haven.api.fixtures import FixtureBackend
from haven.config import UPLOAD_DIR, UPLOAD_MAX_BYTES
from haven.cost import CostReferences, estimate_monthly_cost, load_cost_references
from haven.domain import CostBreakdown, SuitabilityAssessment, Upload, UploadKind
from haven.location import CachedProvider
from haven.rules import evaluate_rules, location_for
from haven.store import SeedStore, UploadRejected, UploadStore, load_seed


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
    ) -> None:
        super().__init__(directory)
        self._today = today
        self.location = CachedProvider() if location is None else location
        self.uploads = (
            UploadStore(UPLOAD_DIR, max_bytes=UPLOAD_MAX_BYTES) if uploads is None else uploads
        )
        self._references = references
        self.seed = load_seed() if seed is None else seed
        clash = {p.id for p in self.seed} & self._properties.keys()
        if clash:
            raise ValueError(f"seed property ids clash with fixture ids: {sorted(clash)}")
        self._properties = {**{p.id: p for p in self.seed}, **self._properties}

    def estimate_cost(self, property_id: str, profile_id: str | None) -> CostBreakdown:
        prop = self.get_property(property_id)
        profile = None if profile_id is None else self.get_profile(profile_id)
        return estimate_monthly_cost(prop, profile, on=self._today(), references=self._references())

    def assess_suitability(self, property_id: str, profile_id: str) -> SuitabilityAssessment:
        prop = self.get_property(property_id)
        profile = self.get_profile(profile_id)
        location = location_for(self.location, prop, profile)
        cost = estimate_monthly_cost(prop, profile, on=self._today(), references=self._references())
        return SuitabilityAssessment(
            property_id=prop.id,
            profile_id=profile.id,
            findings=evaluate_rules(prop, profile, location, cost),
        )

    def create_upload(
        self,
        *,
        kind: UploadKind,
        filename: str,
        content_type: str,
        content: bytes,
        property_id: str | None,
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
        self._uploads[upload.id] = upload
        return upload

    def delete_upload(self, upload_id: str) -> None:
        stored = self.uploads.delete(upload_id)
        known = self._uploads.pop(upload_id, None) is not None
        if not (stored or known):
            raise NotFound("upload", upload_id)
