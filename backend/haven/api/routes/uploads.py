"""Uploaded evidence: photos, floor plans and documents."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile

from haven.api import examples as ex
from haven.api.deps import BackendDep
from haven.api.errors import problem_responses
from haven.domain import Upload, UploadKind

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "",
    response_model=Upload,
    status_code=201,
    summary="Upload a photo, floor plan or document",
    description="Multipart upload of a JPEG, PNG, WebP or PDF file (max 15 MB by default). "
    "The type is checked from the file's content, not its name: anything else is rejected "
    "with 415, and larger files with 413. Images are stored with EXIF/GPS metadata removed "
    "(`metadata_stripped: true`); PDFs are stored unchanged. Screening results are possible "
    "signals to inspect, never diagnoses; a signal may be 'insufficient_evidence'. Screening "
    "isn't built yet, so uploads currently have no signals and `evidence_quality: null`. The "
    "fixture backend (`HAVEN_BACKEND=fixtures`) does not store the file at all.",
    responses=ex.json_response(201, ex.per_persona("upload"))
    | problem_responses(404, 413, 415, 422),
)
async def create_upload(
    backend: BackendDep,
    file: Annotated[UploadFile, File(description="The photo, floor plan or document.")],
    kind: Annotated[UploadKind, Form(description="What the file is.")],
    property_id: Annotated[
        str | None, Form(description="Property the evidence is about, if any.")
    ] = None,
) -> Upload:
    content = await file.read()
    return backend.create_upload(
        kind=kind,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        content=content,
        property_id=property_id,
    )


@router.delete(
    "/{upload_id}",
    status_code=204,
    response_class=Response,
    summary="Delete an upload",
    description="Removes the stored file, its record and its derived signals.",
    responses=problem_responses(404, 422),
)
def delete_upload(backend: BackendDep, upload_id: str) -> Response:
    backend.delete_upload(upload_id)
    return Response(status_code=204)
