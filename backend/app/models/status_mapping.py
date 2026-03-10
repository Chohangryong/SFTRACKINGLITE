from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StatusMapping(TimestampMixin, Base):
    __tablename__ = "status_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    carrier_code: Mapped[str] = mapped_column(String, nullable=False, index=True)
    opcode: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    first_status_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    secondary_status_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    mapped_status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
