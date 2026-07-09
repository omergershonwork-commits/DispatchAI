from typing import Literal

from pydantic import BaseModel, Field

IncidentUrgency = Literal["unknown", "low", "medium", "high", "critical"]
"""Allowed urgency labels produced by incident extraction."""


class IncidentExtractionResult(BaseModel):
    """Validated incident details extracted from a free-text Telegram message."""

    is_incident: bool = Field(description="Whether the message appears to describe an incident requiring help.")
    summary: str = Field(description="Short human-readable incident summary.")
    incident_type: str | None = Field(default=None, description="Incident category inferred from the message, when clear.")
    location_text: str | None = Field(default=None, description="Free-text location mentioned by the sender, when available.")
    urgency: IncidentUrgency = Field(default="unknown", description="Estimated urgency level.")
    people_count: int | None = Field(default=None, ge=0, description="Number of affected people, when stated or clearly inferred.")
    contact_name: str | None = Field(default=None, description="Name of the person to contact, when provided.")
    phone_number: str | None = Field(default=None, description="Phone number mentioned by the sender, when provided.")
    needs: list[str] = Field(default_factory=list, description="Concrete needs or resources requested by the sender.")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence in the extracted details.")
