"""Contract metadata."""

from fastapi import APIRouter

from haven.api import examples as ex
from haven.api.meta import enum_catalog
from haven.api.schemas import EnumCatalog

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get(
    "/enums",
    response_model=EnumCatalog,
    summary="Enum values with human-readable labels",
    description="Use these labels instead of showing raw enum values.",
    responses=ex.json_response(200, ex.single(enum_catalog().model_dump(mode="json"), "All enums")),
)
def get_enums() -> EnumCatalog:
    return enum_catalog()
