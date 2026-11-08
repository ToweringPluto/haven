"""Renter profiles."""

from typing import Annotated, Any

from fastapi import APIRouter, Body

from haven.api import examples as ex
from haven.api.auth import OptionalUserDep
from haven.api.deps import BackendDep
from haven.api.errors import problem_responses
from haven.api.schemas import ProfileInput, ProfileList
from haven.domain import RenterProfile

router = APIRouter(prefix="/profiles", tags=["profiles"])

# Signing in is optional on these endpoints: no token is fine, a valid one adds ownership.
OPTIONAL_AUTH: dict[str, Any] = {"security": [{}]}  # FastAPI adds {"Auth0": []} itself


@router.get(
    "",
    response_model=ProfileList,
    summary="List renter profiles",
    openapi_extra=OPTIONAL_AUTH,
    description="The illustrative personas, plus the caller's own saved profiles when the "
    "request carries a valid Auth0 bearer token. Profiles created without signing in are "
    "never listed; they can still be fetched by id.",
    responses=ex.json_response(200, ex.single(ex.profile_list(), "Illustrative personas"))
    | problem_responses(401),
)
def list_profiles(backend: BackendDep, user: OptionalUserDep) -> ProfileList:
    return ProfileList(items=backend.list_profiles(None if user is None else user.sub))


@router.post(
    "",
    response_model=RenterProfile,
    status_code=201,
    summary="Create a renter profile",
    openapi_extra=OPTIONAL_AUTH,
    description="Everything in a profile is stated by the renter. Omitted limits mean "
    "'not stated', not 'no limit'. The server assigns the id. Profiles are saved; with a "
    "valid Auth0 bearer token the profile belongs to that user and appears in their "
    "`GET /v1/profiles` list.",
    responses=ex.json_response(201, ex.per_persona("profile")) | problem_responses(401, 422),
)
def create_profile(
    backend: BackendDep,
    user: OptionalUserDep,
    data: Annotated[ProfileInput, Body(openapi_examples=ex.profile_inputs())],
) -> RenterProfile:
    return backend.create_profile(data, None if user is None else user.sub)


@router.get(
    "/{profile_id}",
    response_model=RenterProfile,
    summary="Get a renter profile",
    responses=ex.json_response(200, ex.per_persona("profile")) | problem_responses(404, 422),
)
def get_profile(backend: BackendDep, profile_id: str) -> RenterProfile:
    return backend.get_profile(profile_id)
