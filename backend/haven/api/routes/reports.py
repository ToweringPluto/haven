"""Assessments (creating a report) and reports."""

from typing import Annotated

from fastapi import APIRouter, Body

from haven.api import examples as ex
from haven.api.deps import BackendDep
from haven.api.errors import problem_responses
from haven.api.schemas import AssessmentRequest
from haven.domain import Report

assessments = APIRouter(prefix="/assessments", tags=["reports"])
reports = APIRouter(prefix="/reports", tags=["reports"])

REPORT_DESCRIPTION = (
    "A report combines cost, rule findings and screening signals with a plain-language "
    "explanation whose sentences cite finding/signal ids. Always show `disclaimer`. There "
    "is deliberately no overall score."
)


@assessments.post(
    "",
    response_model=Report,
    status_code=201,
    summary="Assess a property for a renter profile and create a report",
    description=REPORT_DESCRIPTION,
    responses=ex.json_response(201, ex.per_persona("report")) | problem_responses(404, 422, 501),
)
def create_assessment(
    backend: BackendDep,
    data: Annotated[
        AssessmentRequest,
        Body(
            openapi_examples={
                "tight_budget": {
                    "summary": ex.SUMMARIES["tight_budget"],
                    "value": {
                        "profile_id": "persona-tight-budget",
                        "property_id": "ill-prop-gorgie-flat",
                        "upload_ids": ["ill-upload-tb-bathroom"],
                    },
                }
            }
        ),
    ],
) -> Report:
    return backend.create_assessment(data)


@reports.get(
    "/{report_id}",
    response_model=Report,
    summary="Get a report",
    description=REPORT_DESCRIPTION,
    responses=ex.json_response(200, ex.per_persona("report")) | problem_responses(404, 422),
)
def get_report(backend: BackendDep, report_id: str) -> Report:
    return backend.get_report(report_id)
