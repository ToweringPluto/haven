"""Properties, their cost breakdown and their suitability for a renter profile.

Listings are read-only: renters can't add them.
"""

from typing import Annotated

from fastapi import APIRouter, Body

from haven.api import examples as ex
from haven.api.deps import BackendDep
from haven.api.errors import problem_responses
from haven.api.schemas import CostRequest, PropertyList, SuitabilityRequest
from haven.domain import CostBreakdown, Property, SuitabilityAssessment

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get(
    "",
    response_model=PropertyList,
    summary="List properties",
    responses=ex.json_response(200, ex.single(ex.property_list(), "Illustrative properties")),
)
def list_properties(backend: BackendDep) -> PropertyList:
    return PropertyList(items=backend.list_properties())


@router.get(
    "/{property_id}",
    response_model=Property,
    summary="Get a property",
    responses=ex.json_response(200, ex.property_examples()) | problem_responses(404, 422),
)
def get_property(backend: BackendDep, property_id: str) -> Property:
    return backend.get_property(property_id)


@router.post(
    "/{property_id}/cost",
    response_model=CostBreakdown,
    summary="Estimate the true monthly cost of a property",
    description="Rent, council tax, estimated energy and other recurring costs, each with "
    "its provenance. Missing inputs make a line (and the total) 'insufficient'; they are "
    "never counted as zero. Without a profile, the budget comparison is 'unknown'.",
    responses=ex.json_response(200, ex.per_persona("cost")) | problem_responses(404, 422, 501),
)
def estimate_cost(
    backend: BackendDep,
    property_id: str,
    data: Annotated[
        CostRequest,
        Body(
            openapi_examples={
                "student": {
                    "summary": ex.SUMMARIES["student"],
                    "value": {"profile_id": "persona-student"},
                },
                "no_profile": {"summary": "No profile (no budget comparison)", "value": {}},
            }
        ),
    ],
) -> CostBreakdown:
    return backend.estimate_cost(property_id, data.profile_id)


@router.post(
    "/{property_id}/suitability",
    response_model=SuitabilityAssessment,
    summary="Check a property against a renter's requirements",
    description="One finding per applicable rule (meets / concern / unknown), each with its "
    "reason, cited facts and, for concern or unknown, a next step. There is deliberately "
    "no overall score.",
    responses=ex.json_response(200, ex.per_persona("suitability"))
    | problem_responses(404, 422, 501),
)
def assess_suitability(
    backend: BackendDep,
    property_id: str,
    data: Annotated[
        SuitabilityRequest,
        Body(
            openapi_examples={
                "wheelchair_user": {
                    "summary": ex.SUMMARIES["wheelchair_user"],
                    "value": {"profile_id": "persona-wheelchair-user"},
                }
            }
        ),
    ],
) -> SuitabilityAssessment:
    return backend.assess_suitability(property_id, data.profile_id)
