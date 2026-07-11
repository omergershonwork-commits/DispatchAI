from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

INCIDENT_STATUS_PENDING_DETAILS = "pending_details"
"""Incident is waiting for additional sender details before dispatch."""

INCIDENT_STATUS_READY_FOR_DISPATCH = "ready_for_dispatch"
"""Incident has enough details for dispatch matching."""

INCIDENT_STATUS_DISPATCHED = "dispatched"
"""Incident has been sent to volunteers or dispatch operators."""

INCIDENT_STATUS_CLOSED = "closed"
"""Incident has been resolved or manually closed."""


def utc_now() -> datetime:
    """Return the current UTC time for timestamp defaults."""

    return datetime.now(UTC)


class Incident(Base):
    """Persisted incident report extracted from source messages."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="telegram")
    source_update_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_chat_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    incident_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgency: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    casualties_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Deprecated compatibility field for existing data and clients. New code uses casualties_text.
    people_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
