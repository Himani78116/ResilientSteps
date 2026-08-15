from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WasteReportCreate(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude")
    category: str = Field(..., min_length=2, max_length=120, description="Waste category code")
    description: Optional[str] = Field(None, max_length=2000, description="Optional description")
    severity: int = Field(3, ge=1, le=5, description="Severity 1-5")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")


class WasteReportResponse(BaseModel):
    id: str
    status: str
    confidence: float
    submitted_at: Any
    report_type: str = "waste"
    severity: int = 3


class WasteCategoryItem(BaseModel):
    code: str
    label: str
    description: Optional[str] = None
    module: str = "waste"


class WasteCategoryListResponse(BaseModel):
    categories: List[WasteCategoryItem]
