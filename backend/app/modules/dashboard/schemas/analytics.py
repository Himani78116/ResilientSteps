from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CitySummary(BaseModel):
    total_reports: int = Field(0, description="Total reports across all categories and statuses")
    pending_count: int = Field(0, description="Pending reports count")
    verified_count: int = Field(0, description="Verified reports count")
    rejected_count: int = Field(0, description="Rejected reports count")
    by_type: Dict[str, int] = Field(default_factory=dict, description="Counts by report_type")
    by_severity: Dict[int, int] = Field(default_factory=dict, description="Counts by severity 1-5")
    average_verification_hours: Optional[float] = Field(None, description="Average moderation time in hours")


class WardSummary(BaseModel):
    ward_id: str
    ward_name: str
    report_count: int = 0
    avg_severity: float = 0.0
    latest_report_at: Optional[datetime] = None
    breakdown: Dict[str, int] = Field(default_factory=dict, description="Counts by report_type")


class WardReportItem(BaseModel):
    id: str
    user_hash: str
    category: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    status: str
    severity: int
    report_type: str
    submitted_at: Any


class TrendPoint(BaseModel):
    date: str
    count: int
    report_type: str


class HeatmapPoint(BaseModel):
    h3_index: str
    lat: float
    lon: float
    report_type: str
    weight: float
