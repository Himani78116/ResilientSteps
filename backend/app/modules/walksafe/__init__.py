"""
WalkSafe Module Package.
Exposes the combined router for all WalkSafe domain endpoints.
"""

from fastapi import APIRouter

from app.modules.walksafe.routers.admin import router as admin_router
from app.modules.walksafe.routers.reports import router as reports_router
from app.modules.walksafe.routers.routing import router as routing_router

router = APIRouter()
router.include_router(admin_router)
router.include_router(routing_router)
router.include_router(reports_router)

__all__ = ["router"]
