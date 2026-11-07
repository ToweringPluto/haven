"""Versioned API routers."""

from fastapi import APIRouter

from haven.api.routes import account, assist, meta, profiles, properties, reports, uploads

v1 = APIRouter(prefix="/v1")
v1.include_router(profiles.router)
v1.include_router(properties.router)
v1.include_router(uploads.router)
v1.include_router(reports.assessments)
v1.include_router(reports.reports)
v1.include_router(meta.router)
v1.include_router(account.router)
v1.include_router(assist.router)

__all__ = ["v1"]
