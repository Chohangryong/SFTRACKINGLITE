from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TrackingEvent(TimestampMixin, Base):
    __tablename__ = "tracking_events"
    __table_args__ = (UniqueConstraint("tracking_id", "event_time", "opcode", "event_desc"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tracking_id: Mapped[int] = mapped_column(ForeignKey("trackings.id"), nullable=False, index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    event_location: Mapped[str | None] = mapped_column(String, nullable=True)
    opcode: Mapped[str | None] = mapped_column(String, nullable=True)
    first_status_code: Mapped[str | None] = mapped_column(String, nullable=True)
    secondary_status_code: Mapped[str | None] = mapped_column(String, nullable=True)
    first_status_name: Mapped[str | None] = mapped_column(String, nullable=True)
    secondary_status_name: Mapped[str | None] = mapped_column(String, nullable=True)
    event_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    mapped_status: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    raw_event_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    tracking = relationship("Tracking", back_populates="events")
