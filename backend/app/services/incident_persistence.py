from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.incident import (
    INCIDENT_STATUS_PENDING_DETAILS,
    INCIDENT_STATUS_READY_FOR_DISPATCH,
    Incident,
)
from app.schemas.incident import IncidentExtractionResult

PENDING_STATUS = INCIDENT_STATUS_PENDING_DETAILS
READY_STATUS = INCIDENT_STATUS_READY_FOR_DISPATCH


class IncidentPersistenceError(RuntimeError):
    """Raised when incident persistence fails after webhook acceptance."""


@dataclass(frozen=True)
class SourceIncidentContext:
    """Source-agnostic metadata for an inbound incident report."""

    source: str
    source_update_id: int | None
    source_message_id: int | None
    source_chat_id: int
    raw_text: str


@dataclass(frozen=True)
class IncidentPersistenceResult:
    """Outcome returned after creating or updating an incident."""

    incident_id: int
    status: str
    created: bool
    updated: bool


class IncidentPersistenceService:
    """Persist source-agnostic incident extractions into the database."""

    def __init__(self, db: Session) -> None:
        """Create a persistence service bound to one SQLAlchemy session."""

        self.db = db

    def build_extraction_text(self, source_context: SourceIncidentContext) -> str:
        """Combine a follow-up message with the pending incident conversation context."""

        try:
            self._ensure_schema()
            pending_incident = self._find_pending_incident(
                source_context.source,
                source_context.source_chat_id,
            )
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise IncidentPersistenceError("Incident conversation lookup failed.") from exc

        if pending_incident is None:
            return source_context.raw_text

        prior_needs = ", ".join(pending_incident.needs or []) or "unknown"
        return (
            "This is a follow-up message for an existing pending incident.\n"
            f"Existing summary: {pending_incident.summary}\n"
            f"Existing incident type: {pending_incident.incident_type or 'unknown'}\n"
            f"Existing location: {pending_incident.location_text or 'unknown'}\n"
            f"Existing urgency: {pending_incident.urgency}\n"
            f"Existing needs: {prior_needs}\n"
            f"Previous conversation: {pending_incident.raw_text}\n"
            f"Latest sender message: {source_context.raw_text}\n"
            "Merge the latest message with the existing incident. Preserve known facts and only replace them when the latest message clearly corrects them."
        )

    def persist_incident(
        self,
        source_context: SourceIncidentContext,
        extraction: IncidentExtractionResult | None,
    ) -> IncidentPersistenceResult | None:
        """Create or update an incident from source metadata and extraction output."""

        if extraction is None or not extraction.is_incident:
            return None
        if not extraction.should_create_incident and not extraction.should_ask_follow_up:
            return None

        try:
            self._ensure_schema()
            pending_incident = self._find_pending_incident(
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
        """Create known ORM tables when running without migrations in local/dev mode."""

        Base.metadata.create_all(bind=self.db.get_bind())

    def _find_pending_incident(self, source: str, source_chat_id: int) -> Incident | None:
        """Return the latest pending incident for a source conversation."""

        return (
            self.db.query(Incident)
            .filter(
                Incident.source == source,
                Incident.source_chat_id == source_chat_id,
                Incident.status == PENDING_STATUS,
            )
            .order_by(Incident.created_at.desc(), Incident.id.desc())
            .first()
        )

    def _build_incident(
        self,
        source_context: SourceIncidentContext,
        extraction: IncidentExtractionResult,
    ) -> Incident:
        """Build a new incident ORM object from source metadata and extraction."""

        status = self._status_from_extraction(extraction)
        return Incident(
            source=source_context.source,
            source_update_id=source_context.source_update_id,
            source_message_id=source_context.source_message_id,
            source_chat_id=source_context.source_chat_id,
            raw_text=source_context.raw_text,
            summary=extraction.summary,
            incident_type=extraction.incident_type,
            location_text=extraction.location_text,
            urgency=extraction.urgency,
            people_count=extraction.people_count,
            contact_name=extraction.contact_name,
            phone_number=extraction.phone_number,
            needs=list(extraction.needs),
            confidence=extraction.confidence,
            status=status,
            metadata_json={
                "missing_fields": list(extraction.missing_fields),
                "follow_up_question": extraction.follow_up_question,
            },
        )

    def _merge_extraction_into_incident(
        self,
        incident: Incident,
        source_context: SourceIncidentContext,
        extraction: IncidentExtractionResult,
    ) -> None:
        """Merge a follow-up extraction into an existing pending incident."""

        incident.source_update_id = source_context.source_update_id
        incident.source_message_id = source_context.source_message_id
        incident.raw_text = f"{incident.raw_text}\n\n--- follow-up ---\n{source_context.raw_text}"
        incident.summary = self._choose_text(extraction.summary, incident.summary) or incident.summary
        incident.incident_type = self._choose_text(extraction.incident_type, incident.incident_type)
        incident.location_text = self._choose_text(extraction.location_text, incident.location_text)
        incident.urgency = self._choose_urgency(extraction.urgency, incident.urgency)
        incident.people_count = extraction.people_count if extraction.people_count is not None else incident.people_count
        incident.contact_name = self._choose_text(extraction.contact_name, incident.contact_name)
        incident.phone_number = self._choose_text(extraction.phone_number, incident.phone_number)
        incident.needs = self._merge_needs(incident.needs, extraction.needs)
        incident.confidence = max(incident.confidence, extraction.confidence)
        incident.metadata_json = {
            "missing_fields": list(extraction.missing_fields),
            "follow_up_question": extraction.follow_up_question,
        }
        if extraction.should_create_incident or self._has_required_fields(incident):
            incident.status = READY_STATUS
        else:
            incident.status = PENDING_STATUS

    def _status_from_extraction(self, extraction: IncidentExtractionResult) -> str:
        """Return the incident status implied by extraction completeness."""

        return READY_STATUS if extraction.should_create_incident else PENDING_STATUS

    def _has_required_fields(self, incident: Incident) -> bool:
        """Return whether the stored incident has enough details for dispatch."""

        return bool(incident.summary and incident.location_text and incident.needs)

    def _choose_text(self, new_value: str | None, current_value: str | None) -> str | None:
        """Prefer a non-empty new text value, otherwise preserve the current value."""

        if new_value and new_value.strip():
            return new_value.strip()
        return current_value

    def _choose_urgency(self, new_value: str, current_value: str) -> str:
        """Keep the highest urgency label between the existing and new extraction."""

        ranking = {
            "unknown": 0,
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4,
        }
        return new_value if ranking.get(new_value, 0) >= ranking.get(current_value, 0) else current_value

    def _merge_needs(self, current_needs: list[str] | None, new_needs: list[str]) -> list[str]:
        """Merge need lists while preserving order and removing duplicates."""

        merged: list[str] = []
        for need in [*(current_needs or []), *new_needs]:
            clean_need = need.strip()
            if clean_need and clean_need not in merged:
                merged.append(clean_need)
        return merged
