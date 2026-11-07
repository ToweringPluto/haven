"""The signed-in user."""

from fastapi import APIRouter

from haven.api import examples as ex
from haven.api.auth import CurrentUserDep
from haven.api.errors import problem_responses
from haven.api.schemas import CurrentUser

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
