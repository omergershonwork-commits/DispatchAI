from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

RECOMMENDATION_STATUS_RECOMMENDED = "recommended"
"""Recommendation was generated but no dispatch message was sent automatically."""

RECOMMENDATION_STATUS_DISPATCH_CREATED = "dispatch_created"
"""Recommendation was converted into a volunteer dispatch request."""

RECOMMENDATION_STATUS_SKIPPED = "skipped"
"""Recommendation was skipped by a later manual or automated step."""


def utc_now() -> datetime:
    """Return the current UTC time for timestamp defaults."""

    return datetime.now(UTC)


class DispatchRecommendation(Base):
    """Ranked volunteer recommendation for an incident."""

    __tablename__ = "dispatch_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), nullable=False, index=True)
    volunteer_id: Mapped[int] = mapped_column(ForeignKey("volunteers.id"), nullable=False, index=True)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        default=RECOMMENDATION_STATUS_RECOMMENDED,
    )
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
