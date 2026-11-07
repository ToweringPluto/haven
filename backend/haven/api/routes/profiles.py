"""Renter profiles."""

from typing import Annotated

from fastapi import APIRouter, Body

from haven.api import examples as ex
from haven.api.deps import BackendDep
from haven.api.errors import problem_responses
from haven.api.schemas import ProfileInput, ProfileList
from haven.domain import RenterProfile

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get(
    "",
    response_model=ProfileList,
    summary="List renter profiles",
    responses=ex.json_response(200, ex.single(ex.profile_list(), "Illustrative personas")),
)
def list_profiles(backend: BackendDep) -> ProfileList:
    return ProfileList(items=backend.list_profiles())


@router.post(
    "",
    response_model=RenterProfile,
    status_code=201,
    summary="Create a renter profile",
    description="Everything in a profile is stated by the renter. Omitted limits mean "
    "'not stated', not 'no limit'. The server assigns the id.",
    responses=ex.json_response(201, ex.per_persona("profile")) | problem_responses(422),
)
def create_profile(
    backend: BackendDep,
    data: Annotated[ProfileInput, Body(openapi_examples=ex.profile_inputs())],
) -> RenterProfile:
    return backend.create_profile(data)


@router.get(
    "/{profile_id}",
    response_model=RenterProfile,
    summary="Get a renter profile",
    responses=ex.json_response(200, ex.per_persona("profile")) | problem_responses(404, 422),
)
def get_profile(backend: BackendDep, profile_id: str) -> RenterProfile:
    return backend.get_profile(profile_id)
