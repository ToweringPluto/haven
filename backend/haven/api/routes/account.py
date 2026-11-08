"""The signed-in user: who they are, their saved homes, and deleting their data."""

from typing import Annotated

from fastapi import APIRouter, Body

from haven.api import examples as ex
from haven.api.auth import CurrentUserDep
from haven.api.deps import BackendDep
from haven.api.errors import problem_responses
from haven.api.schemas import CurrentUser, DeletedData, SavedHomes

router = APIRouter(tags=["account"])


@router.get(
    "/me",
    response_model=CurrentUser,
    summary="Who am I (signed in)",
    description="Returns the verified `sub` and, when the token carries it, the email. "
    "Requires an Auth0 access token for this API.",
    responses=ex.json_response(200, ex.current_user_examples()) | problem_responses(401, 503),
)
def get_me(user: CurrentUserDep) -> CurrentUser:
    return user


@router.delete(
    "/me",
    response_model=DeletedData,
    summary="Delete all my data (signed in)",
    description="Permanently deletes every profile, report, upload (the stored file included) "
    "and saved home that belongs to the signed-in user, and says how many of each were "
    "removed. The Auth0 account itself isn't deleted.",
    responses=ex.json_response(200, ex.deleted_data()) | problem_responses(401, 503),
)
def delete_my_data(backend: BackendDep, user: CurrentUserDep) -> DeletedData:
    return backend.delete_my_data(user.sub)


@router.get(
    "/me/saved-homes",
    response_model=SavedHomes,
    summary="My saved homes (signed in)",
    description="The property ids the signed-in user has saved, in the order saved.",
    responses=ex.json_response(200, ex.saved_homes()) | problem_responses(401, 503),
)
def get_saved_homes(backend: BackendDep, user: CurrentUserDep) -> SavedHomes:
    return SavedHomes(property_ids=backend.get_saved_homes(user.sub))


@router.put(
    "/me/saved-homes",
    response_model=SavedHomes,
    summary="Replace my saved homes (signed in)",
    description="Replaces the whole list. Duplicates are dropped; an unknown property id is `404`.",
    responses=ex.json_response(200, ex.saved_homes()) | problem_responses(401, 404, 422, 503),
)
def set_saved_homes(
    backend: BackendDep,
    user: CurrentUserDep,
    data: Annotated[
        SavedHomes,
        Body(
            openapi_examples={
                "two": {
                    "summary": "Two saved homes",
                    "value": {"property_ids": ["seed-prop-leith", "seed-prop-gorgie"]},
                }
            }
        ),
    ],
) -> SavedHomes:
    return SavedHomes(property_ids=backend.set_saved_homes(user.sub, data.property_ids))
