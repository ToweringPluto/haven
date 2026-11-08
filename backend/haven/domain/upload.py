"""Uploaded evidence (photo or document) and what screening found in it."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from haven.domain.enums import EvidenceQuality, UploadKind
from haven.domain.findings import CitedFact, Signal


class Upload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: UploadKind
    filename: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    uploaded_at: datetime
    property_id: str | None = None
    metadata_stripped: bool = Field(
        description="True when EXIF/GPS metadata was removed from the stored file."
    )
    evidence_quality: EvidenceQuality | None = Field(
        default=None, description="Image quality gate result; null for documents."
    )
    signals: list[Signal] = Field(default_factory=list)
    extracted_facts: list[CitedFact] = Field(
        default_factory=list, description="Facts read from a document, with provenance."
    )
