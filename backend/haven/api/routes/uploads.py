"""Uploaded evidence: photos and documents (signed in)."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile

from haven.api import examples as ex
from haven.api.auth import CurrentUserDep
from haven.api.deps import BackendDep
from haven.api.errors import problem_responses
from haven.api.schemas import UploadList
from haven.domain import Upload, UploadKind

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "",
    response_model=Upload,
    status_code=201,
    summary="Upload a photo or document (signed in)",
    description="Multipart upload of a JPEG, PNG, WebP or PDF file (max 15 MB by default). "
    "The upload belongs to the signed-in user. "
    "The type is checked from the file's content, not its name: anything else is rejected "
    "with 415, and larger files with 413. Images are stored with EXIF/GPS metadata removed "
    "(`metadata_stripped: true`); PDFs are stored unchanged. Photos are screened for possible "
    "issues (signals to inspect, never diagnoses; a signal may be 'insufficient_evidence'), "
    "and documents have their facts extracted. The fixture "
    "backend (`HAVEN_BACKEND=fixtures`) does not store or screen the file.",
    responses=ex.json_response(201, ex.per_persona("upload"))
    | problem_responses(401, 404, 413, 415, 422, 503),
)
async def create_upload(
    backend: BackendDep,
    user: CurrentUserDep,
    file: Annotated[UploadFile, File(description="The photo or document.")],
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
        owner_sub=user.sub,
    )


@router.get(
    "",
    response_model=UploadList,
    summary="List your uploads (signed in)",
    description="The signed-in user's uploads, oldest first, optionally only those about one "
    "property.",
    responses=ex.json_response(200, ex.upload_list()) | problem_responses(401, 422, 503),
)
def list_uploads(
    backend: BackendDep,
    user: CurrentUserDep,
    property_id: Annotated[
        str | None, Query(description="Only uploads about this property.")
    ] = None,
) -> UploadList:
    return UploadList(items=backend.list_uploads(user.sub, property_id))


@router.delete(
    "/{upload_id}",
    status_code=204,
    response_class=Response,
    summary="Delete one of your uploads (signed in)",
    description="Removes the stored file, its record and its derived signals. Other people's "
    "uploads are `404`.",
    responses=problem_responses(401, 404, 422, 503),
)
def delete_upload(backend: BackendDep, user: CurrentUserDep, upload_id: str) -> Response:
    backend.delete_upload(upload_id, user.sub)
    return Response(status_code=204)
