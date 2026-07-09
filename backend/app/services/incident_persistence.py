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
from app.schemas.telegram import TelegramWebhookUpdate

PENDING_STATUS = INCIDENT_STATUS_PENDING_DETAILS
READY_STATUS = INCIDENT_STATUS_READY_FOR_DISPATCH


class IncidentPersistenceError(RuntimeError):
    """Raised when incident persistence fails after webhook acceptance."""


@dataclass(frozen=True)
class IncidentPersistenceResult:
    """Outcome returned after creating or updating an incident."""

    incident_id: int
    """Persisted incident identifier."""

    status: str
    """Persisted incident status after the write."""

    created: bool
    """Whether a new incident row was created."""

    updated: bool
    """Whether an existing pending incident row was updated."""


class IncidentPersistenceService:
    """Persist Telegram incident extractions into the database."""

    def __init__(self, db: Session) -> None:
        """Create a persistence service bound to one SQLAlchemy session."""

        self.db = db

    def persist_from_telegram(
        self,
        update: TelegramWebhookUpdate,
        extraction: IncidentExtractionResult | None,
        raw_text: str,
    ) -> IncidentPersistenceResult | None:
        """Create or update an incident from a Telegram extraction result."""

        if not update.message or extraction is None or not extraction.is_incident:
            return None
        if not extraction.should_create_incident and not extraction.should_ask_follow_up:
            return None

        try:
            self._ensure_schema()
            pending_incident = self._find_pending_incident(update.message.chat.id)

            if pending_incident is not None:
                incident = pending_incident
                self._merge_extraction_into_incident(incident, update, extraction, raw_text)
                created = False
                updated = True
            else:
                incident = self._build_incident(update, extraction, raw_text)
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

    def _find_pending_incident(self, chat_id: int) -> Incident | None:
        """Return the latest pending incident for a Telegram chat, when one exists."""

        return (
            self.db.query(Incident)
            .filter(
                Incident.source == "telegram",
                Incident.source_chat_id == chat_id,
                Incident.status == PENDING_STATUS,
            )
            .order_by(Incident.created_at.desc(), Incident.id.desc())
            .first()
        )

    def _build_incident(
        self,
        update: TelegramWebhookUpdate,
        extraction: IncidentExtractionResult,
        raw_text: str,
    ) -> Incident:
        """Build a new incident ORM object from a Telegram extraction."""

        message = update.message
        if message is None:
            raise ValueError("Telegram message is required to build an incident.")

        status = self._status_from_extraction(extraction)
        return Incident(
            source="telegram",
            source_update_id=update.update_id,
            source_message_id=message.message_id,
            source_chat_id=message.chat.id,
            raw_text=raw_text,
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
        update: TelegramWebhookUpdate,
        extraction: IncidentExtractionResult,
        raw_text: str,
    ) -> None:
        """Merge a follow-up extraction into an existing pending incident."""

        message = update.message
        if message is None:
            raise ValueError("Telegram message is required to update an incident.")

        incident.source_update_id = update.update_id
        incident.source_message_id = message.message_id
        incident.raw_text = f"{incident.raw_text}\n\n--- follow-up ---\n{raw_text}"
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
        incident.status = READY_STATUS if extraction.should_create_incident or self._has_required_fields(incident) else PENDING_STATUS

    def _status_from_extraction(self, extraction: IncidentExtractionResult) -> str:
        """Return the incident status implied by extraction completeness."""

        if extraction.should_create_incident:
            return READY_STATUS
        return PENDING_STATUS

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
