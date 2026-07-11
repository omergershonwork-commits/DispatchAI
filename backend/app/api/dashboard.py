from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.incident import Incident
from app.models.volunteer import (
    DISPATCH_STATUS_ACCEPTED,
    DISPATCH_STATUS_DECLINED,
    DISPATCH_STATUS_DONE,
    DISPATCH_STATUS_EXPIRED,
    DISPATCH_STATUS_SENT,
    Volunteer,
    VolunteerDispatch,
)
from app.schemas.dashboard import (
    AssignedForceItem,
    IncidentDashboardItem,
    VolunteerDashboardItem,
    VolunteerProfileUpdate,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/incidents", response_model=list[IncidentDashboardItem])
def list_incidents(
    incident_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[IncidentDashboardItem]:
    query = db.query(Incident)
    if incident_status:
        query = query.filter(Incident.status == incident_status)
    incidents = query.order_by(Incident.updated_at.desc(), Incident.id.desc()).limit(limit).all()
    return [build_incident_item(incident) for incident in incidents]


@router.get("/incidents/{incident_id}", response_model=IncidentDashboardItem)
def get_incident(incident_id: int, db: Session = Depends(get_db)) -> IncidentDashboardItem:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="incident_not_found")
    return build_incident_item(incident)


@router.get("/volunteers", response_model=list[VolunteerDashboardItem])
def list_volunteers(
    volunteer_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[VolunteerDashboardItem]:
    query = db.query(Volunteer)
    if volunteer_status:
        query = query.filter(Volunteer.status == volunteer_status)
    volunteers = query.order_by(Volunteer.last_seen_at.desc(), Volunteer.id.asc()).limit(limit).all()
    return [build_volunteer_item(db, volunteer) for volunteer in volunteers]


@router.get("/volunteers/{volunteer_id}", response_model=VolunteerDashboardItem)
def get_volunteer(volunteer_id: int, db: Session = Depends(get_db)) -> VolunteerDashboardItem:
    volunteer = db.get(Volunteer, volunteer_id)
    if volunteer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="volunteer_not_found")
    return build_volunteer_item(db, volunteer)


@router.patch("/volunteers/{volunteer_id}", response_model=VolunteerDashboardItem)
def update_volunteer_profile(
    volunteer_id: int,
    update: VolunteerProfileUpdate,
    db: Session = Depends(get_db),
) -> VolunteerDashboardItem:
    volunteer = db.get(Volunteer, volunteer_id)
    if volunteer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="volunteer_not_found")

    changes = update.dict(exclude_unset=True)
    for field in ("display_name", "phone_number", "gender", "height_cm", "weight_kg", "trust_score"):
        if field in changes:
            setattr(volunteer, field, changes[field])

    if "inventory" in changes:
        volunteer.inventory = clean_string_list(changes["inventory"] or [])

    metadata = dict(volunteer.metadata_json or {})
    if "phone_number" in changes:
        metadata["phone_number"] = changes["phone_number"]
    volunteer.metadata_json = metadata

    db.commit()
    db.refresh(volunteer)
    return build_volunteer_item(db, volunteer)


def build_incident_item(incident: Incident) -> IncidentDashboardItem:
    metadata = incident.metadata_json or {}
    raw_forces = metadata.get("assigned_forces")
    assigned_forces: list[AssignedForceItem] = []
    if isinstance(raw_forces, list):
        for raw_force in raw_forces:
            if not isinstance(raw_force, dict):
                continue
            try:
                assigned_forces.append(AssignedForceItem.parse_obj(raw_force))
            except (TypeError, ValueError):
                continue

    casualties_text = incident.casualties_text
    if not casualties_text and incident.people_count is not None:
        casualties_text = f"{incident.people_count} affected"

    return IncidentDashboardItem(
        id=incident.id,
        title=incident.title or fallback_title(incident),
        summary=incident.summary,
        incident_type=incident.incident_type,
        location_text=incident.location_text,
        urgency=incident.urgency,
        casualties_text=casualties_text,
        needs=list(incident.needs or []),
        confidence=float(incident.confidence or 0.0),
        status=incident.status,
        assigned_forces=assigned_forces,
        contact_name=incident.contact_name,
        phone_number=incident.phone_number,
        source=incident.source,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )


def build_volunteer_item(db: Session, volunteer: Volunteer) -> VolunteerDashboardItem:
    metadata = volunteer.metadata_json or {}
    completed = (
        db.query(VolunteerDispatch)
        .filter(
            VolunteerDispatch.volunteer_id == volunteer.id,
            VolunteerDispatch.status == DISPATCH_STATUS_DONE,
        )
        .count()
    )
    declined = (
        db.query(VolunteerDispatch)
        .filter(
            VolunteerDispatch.volunteer_id == volunteer.id,
            VolunteerDispatch.status == DISPATCH_STATUS_DECLINED,
        )
        .count()
    )
    expired = (
        db.query(VolunteerDispatch)
        .filter(
            VolunteerDispatch.volunteer_id == volunteer.id,
            VolunteerDispatch.status == DISPATCH_STATUS_EXPIRED,
        )
        .count()
    )
    active_dispatch = (
        db.query(VolunteerDispatch)
        .filter(
            VolunteerDispatch.volunteer_id == volunteer.id,
            VolunteerDispatch.status.in_([DISPATCH_STATUS_SENT, DISPATCH_STATUS_ACCEPTED]),
        )
        .order_by(VolunteerDispatch.updated_at.desc(), VolunteerDispatch.id.desc())
        .first()
    )

    inventory = volunteer.inventory or metadata.get("inventory") or []
    return VolunteerDashboardItem(
        id=volunteer.id,
        display_name=volunteer.display_name,
        username=volunteer.source_username,
        phone_number=volunteer.phone_number or metadata.get("phone_number"),
        status=volunteer.status,
        gender=volunteer.gender,
        height_cm=volunteer.height_cm,
        weight_kg=volunteer.weight_kg,
        trust_score=float(volunteer.trust_score if volunteer.trust_score is not None else 0.5),
        inventory=clean_string_list(inventory),
        skills=clean_string_list(metadata.get("skills") or []),
        service_areas=clean_string_list(metadata.get("service_areas") or []),
        vehicle=metadata.get("vehicle"),
        max_distance_km=metadata.get("max_distance_km"),
        last_seen_at=volunteer.last_seen_at,
        registered_at=volunteer.registered_at,
        completed_dispatches=completed,
        declined_dispatches=declined,
        expired_offers=expired,
        active_dispatch_status=active_dispatch.status if active_dispatch else None,
    )


def fallback_title(incident: Incident) -> str:
    candidate = (incident.incident_type or incident.summary or "Incident report").replace("_", " ")
    words = candidate.split()
    return " ".join(words[:4]) or "Incident report"


def clean_string_list(values: list[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        text_value = str(value).strip()
        if text_value and text_value not in result:
            result.append(text_value)
    return result
