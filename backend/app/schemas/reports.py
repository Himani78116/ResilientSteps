from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ReportCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    user_hash: str = Field(default="anonymous", min_length=2, max_length=128)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    category: str = Field(
        min_length=2,
        max_length=120,
        validation_alias=AliasChoices("category", "incident_type"),
    )
    description: Optional[str] = Field(default=None, max_length=2000)
    severity: int = Field(default=3, ge=1, le=5)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReportResponse(BaseModel):
    id: str
    status: str
    message: str


class RecentReport(BaseModel):
    id: str
    lat: float
    lon: float
    incident_type: str
    severity: int
    confidence_score: float
    created_at: datetime
    status: str


class TrustedContactPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=1, max_length=32)


class EmergencyAlertCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_hash: str = Field(min_length=2, max_length=128)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    message: Optional[str] = None
    trusted_contacts: list[str | TrustedContactPayload] = Field(
        default_factory=list,
        max_length=10,
    )
    contacts_notified: int = Field(default=0, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EmergencyAlertResponse(BaseModel):
    id: str
    status: str
    created_at: Optional[datetime] = None
    message: str
    contacts_notified: int = 0
    trusted_contacts: list[str | TrustedContactPayload] = Field(default_factory=list)
