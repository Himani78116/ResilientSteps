from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import require_auth
from app.core.database import get_db
from app.core.rate_limiter import report_rate_limiter
from app.modules.infrastructure.schemas.reports import (
    InfraCategoryItem,
    InfraReportCreate,
    InfraReportResponse,
)
from app.modules.infrastructure.services.infra_reporting_service import (
    infra_reporting_service,
)

router = APIRouter(tags=["Infrastructure"])


@router.post("/reports", response_model=InfraReportResponse)
async def create_infra_report(
    payload: InfraReportCreate,
    db: AsyncSession = Depends(get_db),
    user_hash: str = Depends(require_auth),
    _: None = Depends(report_rate_limiter),
):
    """
    Submit a citizen infrastructure issue report (pothole, streetlight, etc.).
    Requires Bearer auth token and is rate limited (5/hr).
    """
    return await infra_reporting_service.create_report(payload, user_hash, db)


@router.get("/reports/recent", response_model=List[Dict[str, Any]])
async def get_recent_infra_reports(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get recent verified infrastructure reports.
    """
    return await infra_reporting_service.get_recent_reports(limit=limit, db=db)


@router.get("/categories", response_model=List[InfraCategoryItem])
async def get_infra_categories(
    db: AsyncSession = Depends(get_db),
):
    """
    Get available infrastructure report categories.
    """
    return await infra_reporting_service.get_categories(db)
