from datetime import UTC, datetime
from typing import Any

from app.models.incident import Incident
from app.models.volunteer import Volunteer


def sync_assigned_force(
    incident: Incident | None,
    volunteer: Volunteer | None,
    status: str,
    dispatch_id: int | None = None,
    distance: str | None = None,
    distance_km: float | None = None,
) -> None:
    """Upsert one volunteer's latest assignment state in incident metadata."""

    if incident is None or volunteer is None:
        return

    metadata = dict(incident.metadata_json or {})
    current = metadata.get("assigned_forces")
    assigned_forces = [dict(item) for item in current if isinstance(item, dict)] if isinstance(current, list) else []

    resolved_distance = distance
    if distance_km is not None:
        resolved_distance = f"{float(distance_km):.1f} km"

    entry: dict[str, Any] = {
        "volunteer_id": volunteer.id,
        "name": volunteer.display_name or volunteer.source_username or f"Volunteer {volunteer.id}",
        "status": status,
        "distance": resolved_distance if resolved_distance is not None else volunteer_distance_text(volunteer),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if distance_km is not None:
        entry["distance_km"] = round(float(distance_km), 3)
    if dispatch_id is not None:
        entry["dispatch_id"] = dispatch_id

    for index, existing in enumerate(assigned_forces):
        if existing.get("volunteer_id") == volunteer.id:
            assigned_forces[index] = {**existing, **entry}
            break
    else:
        assigned_forces.append(entry)

    metadata["assigned_forces"] = assigned_forces
    incident.metadata_json = metadata


def volunteer_distance_text(volunteer: Volunteer) -> str | None:
    metadata = volunteer.metadata_json or {}
    for key in ("distance_text", "estimated_distance_text"):
        value = metadata.get(key)
        if value:
            return str(value)

    for key in ("distance_km", "estimated_distance_km"):
        value = metadata.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        return f"{numeric:g} km"
    return None
