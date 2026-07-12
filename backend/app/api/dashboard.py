from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.incident import Incident
from app.models.volunteer import Volunteer, VolunteerDispatch, DISPATCH_STATUS_SENT, DISPATCH_STATUS_ACCEPTED

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
"""Router containing endpoints for the React Tactical Dashboard."""


class IncidentResponse(BaseModel):
    """Dashboard representation of an Incident."""
    id: int
    raw_text: str
    summary: str
    incident_type: str | None = None
    location_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    urgency: str
    people_count: int | None = None
    contact_name: str | None = None
    phone_number: str | None = None
    needs: list[str]
    confidence: float
    status: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VolunteerResponse(BaseModel):
    """Dashboard representation of a Volunteer."""
    id: int
    source_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    status: str
    assigned_incident_id: int | None = None
    dispatch_status: str | None = None
    metadata_json: dict[str, Any]
    registered_at: datetime
    last_seen_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DispatchAssignment(BaseModel):
    """A single volunteer-to-incident assignment for the map."""
    volunteer_id: int
    incident_id: int
    dispatch_status: str


@router.get("/incidents", response_model=list[IncidentResponse])
def get_dashboard_incidents(db: Session = Depends(get_db)):
    """Return incidents for the tactical dashboard (ordered by newest first)."""
    stmt = select(Incident).where(Incident.status != "closed").order_by(Incident.created_at.desc()).limit(100)
    return list(db.scalars(stmt).all())


@router.get("/volunteers", response_model=list[VolunteerResponse])
def get_dashboard_volunteers(db: Session = Depends(get_db)):
    """Return registered volunteers with their active dispatch assignment."""
    volunteers = list(db.scalars(
        select(Volunteer).order_by(Volunteer.registered_at.desc()).limit(500)
    ).all())

    # Build a map of volunteer_id -> active dispatch
    vol_ids = [v.id for v in volunteers]
    active_dispatches = {}
    if vol_ids:
        dispatches = db.execute(
            select(VolunteerDispatch)
            .join(Incident, VolunteerDispatch.incident_id == Incident.id)
            .where(
                VolunteerDispatch.volunteer_id.in_(vol_ids),
                VolunteerDispatch.status.in_([DISPATCH_STATUS_SENT, DISPATCH_STATUS_ACCEPTED]),
                Incident.status != "closed"
            )
            .order_by(VolunteerDispatch.created_at.desc())
        ).scalars().all()
        for d in dispatches:
            if d.volunteer_id not in active_dispatches:
                active_dispatches[d.volunteer_id] = d

    results = []
    for v in volunteers:
        dispatch = active_dispatches.get(v.id)
        results.append(VolunteerResponse(
            id=v.id,
            source_username=v.source_username,
            first_name=v.first_name,
            last_name=v.last_name,
            display_name=v.display_name,
            status=v.status,
            assigned_incident_id=dispatch.incident_id if dispatch else None,
            dispatch_status=dispatch.status if dispatch else None,
            metadata_json=v.metadata_json,
            registered_at=v.registered_at,
            last_seen_at=v.last_seen_at,
        ))
    return results


@router.get("/assignments", response_model=list[DispatchAssignment])
def get_dispatch_assignments(db: Session = Depends(get_db)):
    """Return all active dispatch assignments for drawing lines on the map."""
    dispatches = db.execute(
        select(VolunteerDispatch)
        .join(Incident, VolunteerDispatch.incident_id == Incident.id)
        .where(
            VolunteerDispatch.status.in_([DISPATCH_STATUS_SENT, DISPATCH_STATUS_ACCEPTED]),
            Incident.status != "closed"
        )
        .order_by(VolunteerDispatch.created_at.desc())
    ).scalars().all()
    return [
        DispatchAssignment(
            volunteer_id=d.volunteer_id,
            incident_id=d.incident_id,
            dispatch_status=d.status,
        )
        for d in dispatches
        if d.incident_id is not None
    ]
