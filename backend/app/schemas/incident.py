from typing import Literal

from pydantic import BaseModel, Field

IncidentUrgency = Literal["unknown", "low", "medium", "high", "critical"]

IncidentMissingField = Literal[
    "incident_type",
    "location_text",
    "casualties_text",
    "people_count",
    "contact_name",
    "phone_number",
    "needs",
]

INCIDENT_ONLY_REPLY = (
    "This bot is only for reporting help or rescue incidents. "
    "Please describe what happened, where it happened, and what help is needed."
)


class IncidentExtractionResult(BaseModel):
    """Validated structured data extracted from a source message."""

    is_incident: bool
    title: str = Field(default="Incident report", min_length=2, max_length=160)
    summary: str
    incident_type: str | None = None
    location_text: str | None = None
    urgency: IncidentUrgency = "unknown"
    casualties_text: str | None = None
    people_count: int | None = Field(default=None, ge=0)
    contact_name: str | None = None
    phone_number: str | None = None
    needs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_fields: list[IncidentMissingField] = Field(default_factory=list)
    follow_up_question: str | None = None
    should_create_incident: bool = False
    should_ask_follow_up: bool = False
    rejection_reason: str | None = None
