from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Tracking(TimestampMixin, Base):
    __tablename__ = "trackings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tracking_number: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    current_status: Mapped[str] = mapped_column(String, nullable=False, default="REGISTERED")
    current_status_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    current_status_code: Mapped[str | None] = mapped_column(String, nullable=True)
    last_event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_event_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    last_event_location: Mapped[str | None] = mapped_column(String, nullable=True)
    last_opcode: Mapped[str | None] = mapped_column(String, nullable=True)
    last_queried_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    order_trackings = relationship("OrderTracking", back_populates="tracking", cascade="all, delete-orphan")
    events = relationship("TrackingEvent", back_populates="tracking", cascade="all, delete-orphan")
