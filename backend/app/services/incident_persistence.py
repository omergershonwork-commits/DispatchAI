from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.incident import (
    INCIDENT_STATUS_CLOSED,
    INCIDENT_STATUS_PENDING_DETAILS,
    INCIDENT_STATUS_READY_FOR_DISPATCH,
    Incident,
)
from app.schemas.incident import IncidentExtractionResult

PENDING_STATUS = INCIDENT_STATUS_PENDING_DETAILS
READY_STATUS = INCIDENT_STATUS_READY_FOR_DISPATCH
CLOSED_STATUS = INCIDENT_STATUS_CLOSED
DEFAULT_PENDING_CONTEXT_TTL_MINUTES = 15


class IncidentPersistenceError(RuntimeError):
    """Raised when incident persistence fails after webhook acceptance."""


@dataclass(frozen=True)
class SourceIncidentContext:
    source: str
    source_update_id: int | None
    source_message_id: int | None
    source_chat_id: int
    raw_text: str
    latitude: float | None = None
    longitude: float | None = None
    location_source: str | None = None


@dataclass(frozen=True)
class IncidentPersistenceResult:
    incident_id: int
    status: str
    created: bool
    updated: bool


class IncidentPersistenceService:
    """Persist source-agnostic incident extractions and conversation state."""

    def __init__(self, db: Session, pending_context_ttl_minutes: int = DEFAULT_PENDING_CONTEXT_TTL_MINUTES) -> None:
        if pending_context_ttl_minutes <= 0:
            raise ValueError("Pending incident context TTL must be positive.")
        self.db = db
        self.pending_context_ttl = timedelta(minutes=pending_context_ttl_minutes)

    def build_extraction_text(self, source_context: SourceIncidentContext) -> str:
        try:
            self._ensure_schema()
            pending_incident = self._find_recent_pending_incident(
                source_context.source,
                source_context.source_chat_id,
            )
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise IncidentPersistenceError("Incident conversation lookup failed.") from exc

        latest_message = source_context.raw_text
        if source_context.latitude is not None and source_context.longitude is not None:
            latest_message = (
                f"{latest_message}\nSender shared GPS coordinates: "
                f"{source_context.latitude:.6f}, {source_context.longitude:.6f}."
            )
        if pending_incident is None:
            return latest_message

        prior_needs = ", ".join(pending_incident.needs or []) or "unknown"
        return (
            "This is a follow-up message for an existing pending incident.\n"
            f"Existing title: {pending_incident.title or 'unknown'}\n"
            f"Existing summary: {pending_incident.summary}\n"
            f"Existing incident type: {pending_incident.incident_type or 'unknown'}\n"
            f"Existing location: {pending_incident.location_text or 'unknown'}\n"
            f"Existing urgency: {pending_incident.urgency}\n"
            f"Existing affected-person details: {pending_incident.casualties_text or 'unknown'}\n"
            f"Existing needs: {prior_needs}\n"
            f"Previous conversation: {pending_incident.raw_text}\n"
            f"Latest sender message: {latest_message}\n"
            "Merge the latest message with the existing incident. Preserve known facts unless the latest message clearly corrects them."
        )

    def close_pending_incident(self, source: str, source_chat_id: int) -> bool:
        try:
            self._ensure_schema()
            incident = self._find_pending_incident(source, source_chat_id)
            if incident is None:
                return False
            incident.status = CLOSED_STATUS
            metadata = dict(incident.metadata_json or {})
            metadata["closed_reason"] = "conversation_reset"
            incident.metadata_json = metadata
            self.db.commit()
            return True
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise IncidentPersistenceError("Pending incident reset failed.") from exc

    def persist_incident(
        self,
        source_context: SourceIncidentContext,
        extraction: IncidentExtractionResult | None,
    ) -> IncidentPersistenceResult | None:
        if extraction is None or not extraction.is_incident:
            return None
        if not extraction.should_create_incident and not extraction.should_ask_follow_up:
            return None

        try:
            self._ensure_schema()
            pending_incident = self._find_recent_pending_incident(
                source_context.source,
                source_context.source_chat_id,
            )

            if pending_incident is not None:
                incident = pending_incident
                self._merge_extraction_into_incident(incident, source_context, extraction)
                created = False
                updated = True
            else:
                incident = self._build_incident(source_context, extraction)
                self.db.add(incident)
                created = True
                updated = False

            self.db.commit()
            self.db.refresh(incident)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise IncidentPersistenceError("Incident persistence failed.") from exc

        return IncidentPersistenceResult(
            incident_id=incident.id,
            status=incident.status,
            created=created,
            updated=updated,
        )

    def _ensure_schema(self) -> None:
        Base.metadata.create_all(bind=self.db.get_bind())

    def _find_recent_pending_incident(self, source: str, source_chat_id: int) -> Incident | None:
        incident = self._find_pending_incident(source, source_chat_id)
        if incident is None:
            return None
        updated_at = incident.updated_at or incident.created_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        if updated_at < datetime.now(UTC) - self.pending_context_ttl:
            return None
        return incident

    def _find_pending_incident(self, source: str, source_chat_id: int) -> Incident | None:
        return (
            self.db.query(Incident)
            .filter(
                Incident.source == source,
                Incident.source_chat_id == source_chat_id,
                Incident.status == PENDING_STATUS,
            )
            .order_by(Incident.updated_at.desc(), Incident.created_at.desc(), Incident.id.desc())
            .first()
        )

    def _build_incident(self, source_context: SourceIncidentContext, extraction: IncidentExtractionResult) -> Incident:
        return Incident(
            source=source_context.source,
            source_update_id=source_context.source_update_id,
            source_message_id=source_context.source_message_id,
            source_chat_id=source_context.source_chat_id,
            raw_text=source_context.raw_text,
            title=extraction.title,
            summary=extraction.summary,
            incident_type=extraction.incident_type,
            location_text=extraction.location_text,
            latitude=source_context.latitude,
            longitude=source_context.longitude,
            location_source=source_context.location_source,
            urgency=extraction.urgency,
            casualties_text=extraction.casualties_text,
            people_count=extraction.people_count,
            contact_name=extraction.contact_name,
            phone_number=extraction.phone_number,
            needs=list(extraction.needs),
            confidence=extraction.confidence,
            status=READY_STATUS if extraction.should_create_incident else PENDING_STATUS,
            metadata_json={
                "missing_fields": list(extraction.missing_fields),
                "follow_up_question": extraction.follow_up_question,
                "assigned_forces": [],
            },
        )

    def _merge_extraction_into_incident(
        self,
        incident: Incident,
        source_context: SourceIncidentContext,
        extraction: IncidentExtractionResult,
    ) -> None:
        incident.source_update_id = source_context.source_update_id
        incident.source_message_id = source_context.source_message_id
        incident.raw_text = f"{incident.raw_text}\n\n--- follow-up ---\n{source_context.raw_text}"
        incident.title = self._choose_text(extraction.title, incident.title)
        incident.summary = self._choose_text(extraction.summary, incident.summary) or incident.summary
        incident.incident_type = self._choose_text(extraction.incident_type, incident.incident_type)
        incident.location_text = self._choose_text(extraction.location_text, incident.location_text)
        if source_context.latitude is not None and source_context.longitude is not None:
            incident.latitude = source_context.latitude
            incident.longitude = source_context.longitude
            incident.location_source = source_context.location_source
        incident.urgency = self._choose_urgency(extraction.urgency, incident.urgency)
        incident.casualties_text = self._choose_text(extraction.casualties_text, incident.casualties_text)
        incident.people_count = extraction.people_count if extraction.people_count is not None else incident.people_count
        incident.contact_name = self._choose_text(extraction.contact_name, incident.contact_name)
        incident.phone_number = self._choose_text(extraction.phone_number, incident.phone_number)
        incident.needs = self._merge_needs(incident.needs, extraction.needs)
        incident.confidence = max(incident.confidence, extraction.confidence)

        metadata = dict(incident.metadata_json or {})
        metadata["missing_fields"] = list(extraction.missing_fields)
        metadata["follow_up_question"] = extraction.follow_up_question
        metadata.setdefault("assigned_forces", [])
        incident.metadata_json = metadata
        incident.status = READY_STATUS if self._has_required_fields(incident) else PENDING_STATUS

    def _has_required_fields(self, incident: Incident) -> bool:
        return bool(incident.summary and incident.incident_type and incident.location_text and incident.needs)

    def _choose_text(self, new_value: str | None, current_value: str | None) -> str | None:
        if new_value and new_value.strip():
            return new_value.strip()
        return current_value

    def _choose_urgency(self, new_value: str, current_value: str) -> str:
        ranking = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        return new_value if ranking.get(new_value, 0) >= ranking.get(current_value, 0) else current_value

    def _merge_needs(self, current_needs: list[str] | None, new_needs: list[str]) -> list[str]:
        merged: list[str] = []
        for need in [*(current_needs or []), *new_needs]:
            clean_need = need.strip()
            if clean_need and clean_need not in merged:
                merged.append(clean_need)
        return merged
