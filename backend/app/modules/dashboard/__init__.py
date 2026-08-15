from fastapi import APIRouter
from app.modules.dashboard.routers.analytics import router as analytics_router
from app.modules.dashboard.routers.management import router as management_router

router = APIRouter()
router.include_router(analytics_router)
router.include_router(management_router)

__all__ = ["router"]
