from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.findings import router as findings_router
from app.api.v1.projects import router as projects_router
from app.api.v1.reports import router as reports_router
from app.api.v1.requests import router as requests_router
from app.api.v1.runs import router as runs_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.system import router as system_router
from app.api.v1.targets import router as targets_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(projects_router)
api_router.include_router(targets_router)
api_router.include_router(sessions_router)
api_router.include_router(admin_router)
api_router.include_router(requests_router)
api_router.include_router(runs_router)
api_router.include_router(findings_router)
api_router.include_router(reports_router)
