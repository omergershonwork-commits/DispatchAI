from typing import Literal

from pydantic import BaseModel, Field

IncidentUrgency = Literal["unknown", "low", "medium", "high", "critical"]
"""Allowed urgency labels produced by incident extraction."""

IncidentMissingField = Literal[
    "incident_type",
    "location_text",
    "people_count",
    "contact_name",
    "phone_number",
    "needs",
]
"""Incident fields that may require a follow-up question."""

INCIDENT_ONLY_REPLY = (
    "This bot is only for reporting help or rescue incidents. "
    "Please describe what happened, where it happened, and what help is needed."
)
"""Fixed reply for messages that are unrelated to incident reporting."""


class IncidentExtractionResult(BaseModel):
    """Validated incident details extracted from a free-text Telegram message."""

    reasoning: str | None = Field(default=None, description="Step-by-step analysis of the emergency.")
    is_incident: bool = Field(description="Whether the message appears to describe an incident requiring help.")
    summary: str = Field(description="Short human-readable incident summary.")
    incident_type: str | None = Field(default=None, description="Incident category inferred from the message, when clear.")
    location_text: str | None = Field(default=None, description="Free-text location mentioned by the sender, when available.")
    latitude: float | None = Field(default=None, description="Evaluated latitude from location_text.")
    longitude: float | None = Field(default=None, description="Evaluated longitude from location_text.")
    urgency: IncidentUrgency = Field(default="unknown", description="Estimated urgency level.")
    people_count: int | None = Field(default=None, ge=0, description="Number of affected people, when stated or clearly inferred.")
    contact_name: str | None = Field(default=None, description="Name of the person to contact, when provided.")
    phone_number: str | None = Field(default=None, description="Phone number mentioned by the sender, when provided.")
    needs: list[str] = Field(default_factory=list, description="Concrete needs or resources requested by the sender.")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence in the extracted details.")
    missing_fields: list[IncidentMissingField] = Field(default_factory=list, description="Important fields still needed from the sender.")
    follow_up_question: str | None = Field(default=None, description="Focused question to ask the sender when critical details are missing.")
    should_create_incident: bool = Field(default=False, description="Whether the current data is enough to create an incident later.")
    should_ask_follow_up: bool = Field(default=False, description="Whether the backend should ask the sender for more details.")
    rejection_reason: str | None = Field(default=None, description="Reason for rejecting non-incident or unsupported messages.")
