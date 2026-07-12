from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

VOLUNTEER_STATUS_AVAILABLE = "available"
VOLUNTEER_STATUS_PENDING_RESPONSE = "pending_response"
VOLUNTEER_STATUS_BUSY = "busy"
VOLUNTEER_STATUS_INACTIVE = "inactive"

DISPATCH_STATUS_SENT = "sent"
DISPATCH_STATUS_ACCEPTED = "accepted"
DISPATCH_STATUS_DECLINED = "declined"
DISPATCH_STATUS_EXPIRED = "expired"
DISPATCH_STATUS_DONE = "done"
DISPATCH_STATUS_CANCELLED = "cancelled"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Volunteer(Base):
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
    phone_number: Mapped[str | None] = mapped_column(String(64), nullable=True)

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    location_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    inventory: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class VolunteerDispatch(Base):
    __tablename__ = "volunteer_dispatches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    volunteer_id: Mapped[int] = mapped_column(ForeignKey("volunteers.id"), nullable=False, index=True)
    incident_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default=DISPATCH_STATUS_SENT)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
