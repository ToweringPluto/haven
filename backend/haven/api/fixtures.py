"""``FixtureBackend``: serves the illustrative persona examples in ``contracts/examples``.

It is a stand-in so the frontend team can build against the contract before the
real engines exist. It never invents numbers: anything a fixture doesn't cover
(e.g. the cost of a property a client created) raises ``NotAvailable`` (501).
State created through the API (profiles, properties, uploads) lives in memory
for the lifetime of the backend instance.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath

from haven.api.errors import NotAvailable, NotFound
from haven.api.schemas import AssessmentRequest, ProfileInput, PropertyInput, PropertyList
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

    # --- profiles ----------------------------------------------------------------------

    def list_profiles(self) -> list[RenterProfile]:
        return list(self._profiles.values())

    def create_profile(self, data: ProfileInput) -> RenterProfile:
        profile = RenterProfile.model_validate({"id": _new_id("profile"), **data.model_dump()})
        self._profiles[profile.id] = profile
        return profile

    def get_profile(self, profile_id: str) -> RenterProfile:
        try:
            return self._profiles[profile_id]
        except KeyError:
            raise NotFound("profile", profile_id) from None

    # --- properties --------------------------------------------------------------------

    def list_properties(self) -> list[Property]:
        return list(self._properties.values())

    def create_property(self, data: PropertyInput) -> Property:
        prop = Property.model_validate({"id": _new_id("property"), **data.model_dump()})
        self._properties[prop.id] = prop
        return prop

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
        self._uploads[upload.id] = upload
        return upload

    def delete_upload(self, upload_id: str) -> None:
        if self._uploads.pop(upload_id, None) is None:
            raise NotFound("upload", upload_id)

    # --- reports -----------------------------------------------------------------------

    def create_assessment(self, data: AssessmentRequest) -> Report:
        self.get_profile(data.profile_id)
        self.get_property(data.property_id)
        for upload_id in data.upload_ids:
            if upload_id not in self._uploads:
                raise NotFound("upload", upload_id)
        report = self._persona_for(data.property_id, data.profile_id).report
        self._reports[report.id] = report
        return report

    def get_report(self, report_id: str) -> Report:
        try:
            return self._reports[report_id]
        except KeyError:
            raise NotFound("report", report_id) from None
