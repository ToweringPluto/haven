"""The ``Backend`` protocol the routers call.

Each method maps to one endpoint, so a real engine can replace the fixture
implementation one endpoint at a time (e.g. a backend that delegates cost to the
cost engine and everything else to ``FixtureBackend``). Methods raise
``haven.api.errors.NotFound`` / ``NotAvailable`` instead of returning placeholders.
"""

from typing import Protocol

from haven.api.schemas import (
    AssessmentRequest,
    PhotoScreen,
    ProfileInput,
    PropertyInput,
)
from haven.domain import (
    CostBreakdown,
    Property,
    RenterProfile,
    Report,
    SuitabilityAssessment,
    Upload,
    UploadKind,
)


class Backend(Protocol):
    def list_profiles(self) -> list[RenterProfile]: ...

    def create_profile(self, data: ProfileInput) -> RenterProfile: ...

    def get_profile(self, profile_id: str) -> RenterProfile: ...

    def list_properties(self) -> list[Property]: ...

    def create_property(self, data: PropertyInput) -> Property: ...

    def get_property(self, property_id: str) -> Property: ...

    def estimate_cost(self, property_id: str, profile_id: str | None) -> CostBreakdown: ...

    def assess_suitability(self, property_id: str, profile_id: str) -> SuitabilityAssessment: ...

    def create_upload(
        self,
        *,
        kind: UploadKind,
        filename: str,
        content_type: str,
        content: bytes,
        property_id: str | None,
    ) -> Upload: ...

    def delete_upload(self, upload_id: str) -> None: ...

    def create_assessment(self, data: AssessmentRequest) -> Report: ...

    def get_report(self, report_id: str) -> Report: ...

    def screen_photo(self, *, content: bytes, content_type: str) -> PhotoScreen:
        """Screen one image held in memory. Must not persist ``content`` anywhere."""
        ...

    def read_aloud(self, text: str) -> bytes:
        """Synthesise ``text`` as MP3 audio."""
        ...
