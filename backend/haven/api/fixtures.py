"""``FixtureBackend``: serves the illustrative persona examples in ``contracts/examples``.

It is a stand-in so the frontend team can build against the contract before the
real engines exist. It never invents numbers: anything a fixture doesn't cover
(e.g. the cost for a profile a client created) raises ``NotAvailable`` (501).
State created through the API (profiles, uploads, reports, saved homes) is kept in a
``RecordStore``: in memory here, in the database on the engine backend when one is set.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath

from pydantic import BaseModel

from haven.api.errors import NotAvailable, NotFound
from haven.api.schemas import (
    AssessmentRequest,
    DeletedData,
    PhotoScreen,
    ProfileInput,
    PropertyList,
    ReportSummary,
)
from haven.domain import (
    BudgetComparison,
    CostBreakdown,
    Property,
    RenterProfile,
    Report,
    SuitabilityAssessment,
    Upload,
    UploadKind,
)
from haven.store.records import MISSING, Kind, MemoryRecordStore, RecordStore

PERSONAS = ("wheelchair_user", "student", "tight_budget")


@dataclass(frozen=True)
class Persona:
    name: str
    profile: RenterProfile
    property: Property
    cost: CostBreakdown
    suitability: SuitabilityAssessment
    upload: Upload
    report: Report


def load_persona(directory: Path, name: str) -> Persona:
    def read(stem: str) -> str:
        return (directory / name / f"{stem}.json").read_text(encoding="utf-8")

    properties = PropertyList.model_validate_json(read("properties")).items
    if len(properties) != 1:
        raise ValueError(f"{name}/properties.json should hold exactly one property")
    return Persona(
        name=name,
        profile=RenterProfile.model_validate_json(read("profile")),
        property=properties[0],
        cost=CostBreakdown.model_validate_json(read("cost")),
        suitability=SuitabilityAssessment.model_validate_json(read("suitability")),
        upload=Upload.model_validate_json(read("upload")),
        report=Report.model_validate_json(read("report")),
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class FixtureBackend:
    def __init__(self, directory: Path) -> None:
        self.personas = [load_persona(directory, name) for name in PERSONAS]
        self._by_property = {p.property.id: p for p in self.personas}
        self._profiles = {p.profile.id: p.profile for p in self.personas}
        self._properties = {p.property.id: p.property for p in self.personas}
        self._uploads = {p.upload.id: p.upload for p in self.personas}
        self._reports = {p.report.id: p.report for p in self.personas}
        self.records: RecordStore = MemoryRecordStore()

    # --- lookups -----------------------------------------------------------------------

    def _persona_for(self, property_id: str, profile_id: str) -> Persona:
        persona = self._by_property.get(property_id)
        if persona is None or persona.profile.id != profile_id:
            raise NotAvailable(
                "The fixture backend only has results for the illustrative persona pairs "
                f"({self._pairs()}); there is no fixture for profile '{profile_id}' with "
                f"property '{property_id}'."
            )
        return persona

    def _pairs(self) -> str:
        return ", ".join(f"{p.profile.id} + {p.property.id}" for p in self.personas)

    def _owned(self, kind: Kind, record_id: str, owner_sub: str) -> None:
        """Raise ``NotFound`` unless ``owner_sub`` owns the record."""
        if self.records.owner(kind, record_id) != owner_sub:
            raise NotFound(kind.replace("_", " "), record_id)

    # --- profiles ----------------------------------------------------------------------

    def list_profiles(self, owner_sub: str | None = None) -> list[RenterProfile]:
        samples = list(self._profiles.values())
        if owner_sub is None:
            return samples  # profiles created without signing in are private to their link
        return samples + self.records.list("profile", RenterProfile, owner_sub=owner_sub)

    def create_profile(self, data: ProfileInput, owner_sub: str | None = None) -> RenterProfile:
        profile = RenterProfile.model_validate({"id": _new_id("profile"), **data.model_dump()})
        self.records.put("profile", profile, owner_sub=owner_sub)
        return profile

    def get_profile(self, profile_id: str) -> RenterProfile:
        profile = self._profiles.get(profile_id) or self.records.get(
            "profile", profile_id, RenterProfile
        )
        if profile is None:
            raise NotFound("profile", profile_id)
        return profile

    def update_profile(self, profile_id: str, data: ProfileInput, owner_sub: str) -> RenterProfile:
        self._owned("profile", profile_id, owner_sub)
        profile = RenterProfile.model_validate({"id": profile_id, **data.model_dump()})
        self.records.put("profile", profile, owner_sub=owner_sub)
        return profile

    def delete_profile(self, profile_id: str, owner_sub: str) -> None:
        self._owned("profile", profile_id, owner_sub)
        self.records.delete("profile", profile_id)

    # --- properties --------------------------------------------------------------------

    def list_properties(self) -> list[Property]:
        return list(self._properties.values())

    def get_property(self, property_id: str) -> Property:
        try:
            return self._properties[property_id]
        except KeyError:
            raise NotFound("property", property_id) from None

    # --- engines (fixture answers) -----------------------------------------------------

    def estimate_cost(self, property_id: str, profile_id: str | None) -> CostBreakdown:
        self.get_property(property_id)
        if profile_id is None:
            persona = self._by_property.get(property_id)
            if persona is None:
                raise NotAvailable(
                    f"The fixture backend has no cost breakdown for property '{property_id}'."
                )
            # Without a profile there is no budget to compare with.
            return persona.cost.model_copy(
                update={
                    "profile_id": None,
                    "budget_monthly_gbp": None,
                    "budget_comparison": BudgetComparison.unknown,
                }
            )
        self.get_profile(profile_id)
        return self._persona_for(property_id, profile_id).cost

    def assess_suitability(self, property_id: str, profile_id: str) -> SuitabilityAssessment:
        self.get_property(property_id)
        self.get_profile(profile_id)
        return self._persona_for(property_id, profile_id).suitability

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
        if property_id is not None:
            self.get_property(property_id)
        # The fixture backend neither stores nor screens the file: no signals, no quality
        # grade and no metadata stripping are claimed.
        upload = Upload(
            id=_new_id("upload"),
            kind=kind,
            filename=PurePath(filename).name or "upload",
            content_type=content_type,
            size_bytes=len(content),
            uploaded_at=datetime.now(UTC),
            property_id=property_id,
            metadata_stripped=False,
            evidence_quality=None,
        )
        self.records.put("upload", upload, owner_sub=owner_sub)
        return upload

    def list_uploads(self, owner_sub: str, property_id: str | None = None) -> list[Upload]:
        uploads = self.records.list("upload", Upload, owner_sub=owner_sub)
        return [u for u in uploads if property_id is None or u.property_id == property_id]

    def _get_upload(self, upload_id: str, owner_sub: str) -> Upload:
        """An example upload (anyone may cite it) or one of the caller's own."""
        if upload_id in self._uploads:
            return self._uploads[upload_id]
        self._owned("upload", upload_id, owner_sub)
        upload = self.records.get("upload", upload_id, Upload)
        if upload is None:
            raise NotFound("upload", upload_id)
        return upload

    def _forget_upload_file(self, upload_id: str) -> None:
        """Remove the stored file, if this backend stores files (the fixture one doesn't)."""

    def delete_upload(self, upload_id: str, owner_sub: str) -> None:
        self._owned("upload", upload_id, owner_sub)
        self._forget_upload_file(upload_id)
        self.records.delete("upload", upload_id)

    # --- reports -----------------------------------------------------------------------

    def _usable_profile(self, profile_id: str, owner_sub: str) -> RenterProfile:
        """A sample profile, one of the caller's own, or one saved without signing in."""
        if profile_id not in self._profiles:
            owner = self.records.owner("profile", profile_id)
            if owner is MISSING or owner not in (None, owner_sub):
                raise NotFound("profile", profile_id)
        return self.get_profile(profile_id)

    def create_assessment(self, data: AssessmentRequest, owner_sub: str) -> Report:
        self._usable_profile(data.profile_id, owner_sub)
        self.get_property(data.property_id)
        for upload_id in data.upload_ids:
            self._get_upload(upload_id, owner_sub)
        return self._persona_for(data.property_id, data.profile_id).report

    def list_reports(self, owner_sub: str) -> list[ReportSummary]:
        reports = self.records.list("report", Report, owner_sub=owner_sub)
        return [
            ReportSummary(
                id=r.id,
                created_at=r.created_at,
                property_id=r.property.id,
                property_title=r.property.title,
                property_area=r.property.area,
                profile_label=r.profile.label,
            )
            for r in sorted(reports, key=lambda r: r.created_at, reverse=True)
        ]

    def get_report(self, report_id: str, owner_sub: str | None) -> Report:
        if report_id in self._reports:
            return self._reports[report_id]
        owner = self.records.owner("report", report_id)
        report = self.records.get("report", report_id, Report)
        # Reports saved before sign-in was required have no owner; they stay readable by id.
        if report is None or (owner is not None and owner != owner_sub):
            raise NotFound("report", report_id)
        return report

    # --- account -----------------------------------------------------------------------

    def get_saved_homes(self, owner_sub: str) -> list[str]:
        saved = self.records.get("saved_homes", owner_sub, SavedHomesRecord)
        return [] if saved is None else saved.property_ids

    def set_saved_homes(self, owner_sub: str, property_ids: list[str]) -> list[str]:
        for property_id in property_ids:
            self.get_property(property_id)
        unique = list(dict.fromkeys(property_ids))
        record = SavedHomesRecord(id=owner_sub, property_ids=unique)
        self.records.put("saved_homes", record, owner_sub=owner_sub)
        return unique

    def delete_my_data(self, owner_sub: str) -> DeletedData:
        for upload in self.records.list("upload", Upload, owner_sub=owner_sub):
            self._forget_upload_file(upload.id)
        kinds = [kind for kind, _ in self.records.delete_owned(owner_sub)]
        return DeletedData(
            profiles=kinds.count("profile"),
            reports=kinds.count("report"),
            uploads=kinds.count("upload"),
            saved_homes="saved_homes" in kinds,
        )

    # --- assistive ---------------------------------------------------------------------

    def screen_photo(self, *, content: bytes, content_type: str) -> PhotoScreen:
        raise NotAvailable(
            "Photo screening isn't available yet: no screening model is connected to this server."
        )

    def read_aloud(self, text: str) -> bytes:
        raise NotAvailable(
            "Read-aloud isn't available yet: no speech service is connected to this server."
        )


class SavedHomesRecord(BaseModel):
    """How a user's saved homes are stored: one record per user, keyed by their ``sub``."""

    id: str
    property_ids: list[str]
