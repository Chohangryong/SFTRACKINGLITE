from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class OrderTracking(TimestampMixin, Base):
    __tablename__ = "order_trackings"
    __table_args__ = (UniqueConstraint("order_id", "tracking_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    tracking_id: Mapped[int] = mapped_column(ForeignKey("trackings.id"), nullable=False, index=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)

    order = relationship("Order", back_populates="order_trackings")
    tracking = relationship("Tracking", back_populates="order_trackings")
