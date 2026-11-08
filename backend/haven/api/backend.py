"""The ``Backend`` protocol the routers call.

Each method maps to one endpoint, so a real engine can replace the fixture
implementation one endpoint at a time (e.g. a backend that delegates cost to the
cost engine and everything else to ``FixtureBackend``). Methods raise
``haven.api.errors.NotFound`` / ``NotAvailable`` instead of returning placeholders.

``owner_sub`` is the Auth0 subject of the signed-in caller. A record that belongs to someone
else is reported as not found, so ids can't be probed.
"""

from typing import Protocol

from haven.api.schemas import (
    AssessmentRequest,
    DeletedData,
    PhotoScreen,
    ProfileInput,
    ReportSummary,
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
    # --- profiles ----------------------------------------------------------------------

    def list_profiles(self, owner_sub: str | None = None) -> list[RenterProfile]:
        """The sample profiles plus those created by the signed-in user ``owner_sub``."""
        ...

    def create_profile(self, data: ProfileInput, owner_sub: str | None = None) -> RenterProfile:
        """Create a profile, owned by ``owner_sub`` when the request was signed in."""
        ...

    def get_profile(self, profile_id: str) -> RenterProfile: ...

    def update_profile(self, profile_id: str, data: ProfileInput, owner_sub: str) -> RenterProfile:
        """Replace one of ``owner_sub``'s own profiles."""
        ...

    def delete_profile(self, profile_id: str, owner_sub: str) -> None: ...

    # --- properties --------------------------------------------------------------------

    def list_properties(self) -> list[Property]: ...

    def get_property(self, property_id: str) -> Property: ...

    def estimate_cost(self, property_id: str, profile_id: str | None) -> CostBreakdown: ...

    def assess_suitability(self, property_id: str, profile_id: str) -> SuitabilityAssessment: ...

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
    ) -> Upload: ...

    def list_uploads(self, owner_sub: str, property_id: str | None = None) -> list[Upload]: ...

    def delete_upload(self, upload_id: str, owner_sub: str) -> None: ...

    # --- reports -----------------------------------------------------------------------

    def create_assessment(self, data: AssessmentRequest, owner_sub: str) -> Report: ...

    def list_reports(self, owner_sub: str) -> list[ReportSummary]:
        """``owner_sub``'s saved reports, newest first."""
        ...

    def get_report(self, report_id: str, owner_sub: str | None) -> Report:
        """An example report (anyone), or one of ``owner_sub``'s own."""
        ...

    # --- account -----------------------------------------------------------------------

    def get_saved_homes(self, owner_sub: str) -> list[str]: ...

    def set_saved_homes(self, owner_sub: str, property_ids: list[str]) -> list[str]: ...

    def delete_my_data(self, owner_sub: str) -> DeletedData:
        """Delete every profile, report, upload (file included) and saved home of the user."""
        ...

    # --- assistive ---------------------------------------------------------------------

    def screen_photo(self, *, content: bytes, content_type: str) -> PhotoScreen:
        """Screen one image held in memory. Must not persist ``content`` anywhere."""
        ...

    def read_aloud(self, text: str) -> bytes:
        """Synthesise ``text`` as MP3 audio."""
        ...
