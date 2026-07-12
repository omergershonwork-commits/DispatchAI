from datetime import datetime

from pydantic import BaseModel, Field


class AssignedForceItem(BaseModel):
    volunteer_id: int
    name: str
    status: str
    distance: str | None = None
    dispatch_id: int | None = None
    updated_at: str | None = None


class IncidentDashboardItem(BaseModel):
    id: int
    title: str
    summary: str
    incident_type: str | None = None
    location_text: str | None = None
    urgency: str
    casualties_text: str | None = None
    needs: list[str] = Field(default_factory=list)
    confidence: float
    status: str
    assigned_forces: list[AssignedForceItem] = Field(default_factory=list)
    contact_name: str | None = None
    phone_number: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime


class VolunteerDashboardItem(BaseModel):
    id: int
    display_name: str | None = None
    username: str | None = None
    phone_number: str | None = None
    status: str
    gender: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    trust_score: float
    inventory: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    service_areas: list[str] = Field(default_factory=list)
    vehicle: str | None = None
    max_distance_km: float | None = None
    last_seen_at: datetime
    registered_at: datetime
    completed_dispatches: int = 0
    declined_dispatches: int = 0
    expired_offers: int = 0
    active_dispatch_status: str | None = None


class VolunteerProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone_number: str | None = Field(default=None, max_length=64)
    gender: str | None = Field(default=None, max_length=32)
    height_cm: float | None = Field(default=None, ge=50, le=260)
    weight_kg: float | None = Field(default=None, ge=20, le=400)
    trust_score: float | None = Field(default=None, ge=0.0, le=1.0)
    inventory: list[str] | None = None
