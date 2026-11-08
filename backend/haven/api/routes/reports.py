"""Assessments (creating a report) and reports. Creating and listing reports needs sign-in."""

from typing import Annotated

from fastapi import APIRouter, Body

from haven.api import examples as ex
from haven.api.auth import CurrentUserDep, OptionalUserDep
from haven.api.deps import BackendDep
from haven.api.errors import problem_responses
from haven.api.schemas import AssessmentRequest, ReportList
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
    summary="Assess a property for a renter profile and create a report (signed in)",
    description=REPORT_DESCRIPTION
    + " The report is saved to the signed-in user's account. The profile must be a sample, "
    "one of theirs, or one saved without signing in; uploads must be theirs.",
    responses=ex.json_response(201, ex.per_persona("report"))
    | problem_responses(401, 404, 422, 501, 503),
)
def create_assessment(
    backend: BackendDep,
    user: CurrentUserDep,
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
    return backend.create_assessment(data, user.sub)


@reports.get(
    "",
    response_model=ReportList,
    summary="List your reports (signed in)",
    description="The signed-in user's saved reports, newest first.",
    responses=ex.json_response(200, ex.report_list()) | problem_responses(401, 503),
)
def list_reports(backend: BackendDep, user: CurrentUserDep) -> ReportList:
    return ReportList(items=backend.list_reports(user.sub))


@reports.get(
    "/{report_id}",
    response_model=Report,
    summary="Get a report",
    openapi_extra={"security": [{}]},
    description=REPORT_DESCRIPTION
    + " Example reports are public. A saved report is only returned to the user who made it "
    "(send the bearer token); anyone else gets `404`.",
    responses=ex.json_response(200, ex.per_persona("report")) | problem_responses(401, 404, 422),
)
def get_report(backend: BackendDep, user: OptionalUserDep, report_id: str) -> Report:
    return backend.get_report(report_id, None if user is None else user.sub)
