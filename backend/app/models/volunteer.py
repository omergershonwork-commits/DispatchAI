from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

VOLUNTEER_STATUS_AVAILABLE = "available"
"""Volunteer is registered and can receive dispatch requests."""

VOLUNTEER_STATUS_BUSY = "busy"
"""Volunteer currently has an active dispatch request."""

VOLUNTEER_STATUS_INACTIVE = "inactive"
"""Volunteer is registered but should not receive dispatch requests."""

DISPATCH_STATUS_SENT = "sent"
"""Dispatch request was sent to a volunteer."""

DISPATCH_STATUS_ACCEPTED = "accepted"
"""Volunteer accepted the dispatch request and is en route."""

DISPATCH_STATUS_DONE = "done"
"""Volunteer marked the dispatch as completed."""

DISPATCH_STATUS_CANCELLED = "cancelled"
"""Dispatch request was cancelled before completion."""


def utc_now() -> datetime:
    """Return the current UTC time for timestamp defaults."""

    return datetime.now(timezone.utc)


class Volunteer(Base):
    """Registered volunteer profile for dispatch communications."""

    __tablename__ = "volunteers"
    __table_args__ = (
        UniqueConstraint("source", "source_chat_id", name="uq_volunteers_source_chat_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="telegram")
    source_chat_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
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


class VolunteerDispatch(Base):
    """Dispatch request sent to a volunteer."""

    __tablename__ = "volunteer_dispatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    volunteer_id: Mapped[int] = mapped_column(ForeignKey("volunteers.id"), nullable=False, index=True)
    incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default=DISPATCH_STATUS_SENT)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
