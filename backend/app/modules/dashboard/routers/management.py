from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.walksafe.routers.admin import list_reports, require_admin

router = APIRouter(tags=["Dashboard Management"])


@router.get("/reports")
async def get_dashboard_reports(
    status: str = "pending",
    report_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    Dashboard report management list with status and report_type filter.
    """
    return await list_reports(status=status, report_type=report_type, db=db, _=_)
